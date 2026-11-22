"""Space boundaries, fair admission and bounded event publication."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from unittest.mock import patch

import pytest
from django.db import close_old_connections, connections
from django.utils import timezone

from chat_analysis import execution, scheduled_dispatch
from chat_analysis.models import (
    AnalysisJob,
    AnalysisJobMessage,
    Event,
    EventSuggestion,
)
from chat_analysis.schedule_window import BEIJING
from chat_analysis.services import retry_analysis_job
from chat_analysis.tasks import (
    execute_analysis_job_task,
    run_due_scheduled_analysis_task,
)
from chat_analysis.tests.test_execution import (
    add_message,
    make_conversation,
    make_job,
    make_space,
)
from chat_analysis.tests.test_scheduled_dispatch import origin
from chat_analysis.tests.test_user_dispatch import user_job
from chat_analysis.user_dispatch import (
    dispatch_lock,
    dispatch_pending_analysis,
)
from chat_domain.models import Message
from chat_ingestion.models import UploadBatch

pytestmark = pytest.mark.django_db(transaction=True)


def model_results(job, messages):
    return {}, [
        {
            "title": f"Case {job.space.slug}",
            "summary": "A specific incident is being investigated.",
            "source_seqs": [row.ingest_seq for row in messages],
        }
    ]


def test_waiting_batch_keeps_its_space_and_defers_other_spaces(
    settings,
    monkeypatch,
):
    settings.CHAT_ANALYSIS_LLM_ENABLED = True
    settings.CHAT_ANALYSIS_AUTO_CREATE_EVENTS = True
    settings.CHAT_ANALYSIS_BATCH_MESSAGES = 10
    monkeypatch.setattr(
        execution, "_messages_for_model", lambda job, rows: rows
    )
    monkeypatch.setattr(execution, "_prepare_chunk", model_results)
    base = user_job("fixed-space")
    owner, first_space, first_chat = (
        base.created_by,
        base.space,
        base.conversation,
    )
    base.delete()
    second_space = make_space(owner, "fixed-space-second")
    second_chat = make_conversation(second_space, "older-upload")
    second_message = add_message(second_chat, 1)
    unfinished = origin(
        second_message,
        owner,
        second_space,
        "older-processing",
        None,
        UploadBatch.Status.PROCESSING,
    )
    origin(
        Message.objects.get(conversation=first_chat),
        owner,
        first_space,
        "first-completed",
        timezone.now(),
    )
    job = scheduled_dispatch.schedule_user(
        owner.pk,
        timezone.now(),
        dispatch=False,
    )
    assert job.space_id == first_space.pk
    UploadBatch.objects.filter(pk=unfinished.pk).update(
        status=UploadBatch.Status.COMPLETED,
        completed_at=timezone.now(),
    )
    with patch("chat_analysis.tasks.execute_analysis_job_task.delay"):
        execute_analysis_job_task.run(job.pk, worker_id="first-space")
    job.refresh_from_db()
    assert job.space_id == first_space.pk
    assert job.conversation_id == first_chat.pk
    assert job.state == AnalysisJob.State.READY
    assert Event.objects.filter(space=first_space).count() == 1
    assert not AnalysisJob.objects.filter(space=second_space).exists()
    assert not hasattr(second_message, "scheduled_analysis")
    # A later user batch may process the historical space independently.
    later = scheduled_dispatch.schedule_user(
        owner.pk,
        timezone.now(),
        dispatch=False,
    )
    assert later.space_id == second_space.pk


def test_admission_rotates_users_before_applying_the_limit(
    settings,
    monkeypatch,
):
    settings.CHAT_ANALYSIS_LLM_ENABLED = True
    settings.CHAT_ANALYSIS_AUTO_CREATE_EVENTS = False
    settings.CHAT_ANALYSIS_DISPATCH_LIMIT = 2
    settings.CHAT_ANALYSIS_BATCH_MESSAGES = 1
    monkeypatch.setattr(
        execution, "_messages_for_model", lambda job, rows: rows
    )
    monkeypatch.setattr(execution, "_prepare_chunk", model_results)
    users, spaces = [], []
    for index, count in enumerate((4, 4, 1)):
        base = user_job(f"fair-admission-{index}", count=count)
        owner, space, chat = base.created_by, base.space, base.conversation
        base.delete()
        users.append(owner.pk)
        spaces.append(space.pk)
        for message in Message.objects.filter(conversation=chat):
            origin(message, owner, space, f"fair-{message.pk}", timezone.now())
    original = scheduled_dispatch._pending_origins

    def own_origins(*args, **kwargs):
        return original(*args, **kwargs).filter(
            message__conversation__space_id__in=spaces,
        )

    monkeypatch.setattr(scheduled_dispatch, "_pending_origins", own_origins)
    first = (timezone.now() + timedelta(hours=1)).replace(
        minute=0,
        second=0,
        microsecond=0,
    )
    rounds = []
    for index in range(2):
        now = first + timedelta(hours=index)
        with (
            patch("django.utils.timezone.now", return_value=now),
            patch("chat_analysis.tasks.execute_analysis_job_task.delay"),
        ):
            scheduled_dispatch.dispatch_due_analysis(
                now,
                now.astimezone(BEIJING).strftime("%H:%M"),
            )
            jobs = list(
                AnalysisJob.objects.filter(
                    created_by_id__in=users,
                    state=AnalysisJob.State.QUEUED,
                ).order_by("pk")
            )
            rounds.append([job.created_by_id for job in jobs])
            for job in jobs:
                execute_analysis_job_task.run(
                    job.pk, worker_id=f"round-{index}"
                )
    assert rounds[0] == users[:2]
    assert users[2] in rounds[1]


def ready_event_batch(key):
    job = user_job(key)
    job.delete()
    owner, space, conversation = job.created_by, job.space, job.conversation
    origin(
        Message.objects.get(conversation=conversation),
        owner,
        space,
        key,
        timezone.now(),
    )
    job = scheduled_dispatch.schedule_user(
        owner.pk,
        timezone.now(),
        dispatch=False,
    )
    return execution.execute_analysis_job(job.pk, worker_id=key).job


def test_publication_drains_ready_batches_within_budget(settings, monkeypatch):
    settings.CHAT_ANALYSIS_LLM_ENABLED = True
    settings.CHAT_ANALYSIS_AUTO_CREATE_EVENTS = True
    monkeypatch.setattr(
        execution, "_messages_for_model", lambda job, rows: rows
    )
    monkeypatch.setattr(execution, "_prepare_chunk", model_results)
    first = ready_event_batch("publish-first")
    second = ready_event_batch("publish-second")
    assert execution.publish_ready_event_batches() == 2
    assert (
        Event.objects.filter(
            space_id__in=(first.space_id, second.space_id)
        ).count()
        == 2
    )
    assert not EventSuggestion.objects.filter(
        analysis_job__in=(first, second),
        status=EventSuggestion.Status.PENDING,
    ).exists()
    assert execution.publish_ready_event_batches() == 0


def test_finishing_batch_publishes_its_own_space_first(settings, monkeypatch):
    settings.CHAT_ANALYSIS_LLM_ENABLED = True
    settings.CHAT_ANALYSIS_AUTO_CREATE_EVENTS = True
    monkeypatch.setattr(
        execution, "_messages_for_model", lambda job, rows: rows
    )
    monkeypatch.setattr(execution, "_prepare_chunk", model_results)
    older = ready_event_batch("older-pending-publication")
    current = user_job("current-publication")
    owner, space, conversation = (
        current.created_by,
        current.space,
        current.conversation,
    )
    current.delete()
    origin(
        Message.objects.get(conversation=conversation),
        owner,
        space,
        "current-publication",
        timezone.now(),
    )
    current = scheduled_dispatch.schedule_user(
        owner.pk,
        timezone.now(),
        dispatch=False,
    )
    with patch("chat_analysis.tasks.execute_analysis_job_task.delay"):
        execute_analysis_job_task.run(current.pk, worker_id="current")
    assert Event.objects.filter(space=space).count() == 1
    assert EventSuggestion.objects.filter(
        analysis_job=older,
        status=EventSuggestion.Status.PENDING,
    ).exists()


def test_publication_stops_when_time_budget_is_exhausted(
    settings, monkeypatch
):
    settings.CHAT_ANALYSIS_LLM_ENABLED = True
    settings.CHAT_ANALYSIS_AUTO_CREATE_EVENTS = True
    monkeypatch.setattr(
        execution, "_messages_for_model", lambda job, rows: rows
    )
    monkeypatch.setattr(execution, "_prepare_chunk", model_results)
    first = ready_event_batch("budget-publish-first")
    second = ready_event_batch("budget-publish-second")
    original = execution._publish_event_batch
    elapsed = [0]

    def publish(*args, **kwargs):
        result = original(*args, **kwargs)
        elapsed[0] = 2
        return result

    with (
        patch.object(execution, "monotonic", side_effect=lambda: elapsed[0]),
        patch.object(execution, "_publish_event_batch", side_effect=publish),
    ):
        assert execution.publish_ready_event_batches(time_limit=1) == 1
    assert EventSuggestion.objects.filter(
        analysis_job=second,
        status=EventSuggestion.Status.PENDING,
    ).exists()
    assert Event.objects.filter(space=first.space).count() == 1
    assert execution.publish_ready_event_batches() == 1


def test_four_users_can_claim_concurrently_but_one_user_stays_exclusive(
    settings,
):
    settings.CHAT_ANALYSIS_MAX_CONCURRENT_USERS = 4
    jobs = [user_job(f"four-users-{i}") for i in range(4)]
    owner = jobs[0].created_by
    for index in range(2):
        space = make_space(owner, f"four-users-extra-{index}")
        chat = make_conversation(space, str(index))
        jobs.append(make_job(space, owner, chat))
    with dispatch_lock():
        pass
    barrier = Barrier(len(jobs))

    def claim(job_id):
        close_old_connections()
        try:
            barrier.wait(timeout=10)
            value = execution.claim_analysis_job(job_id, worker_id=str(job_id))
            return value.created_by_id if value else None
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
        owners = [pk for pk in pool.map(claim, [job.pk for job in jobs]) if pk]
    assert len(owners) == 4
    assert len(set(owners)) == 4
    assert owners.count(owner.pk) == 1


def test_partial_users_share_admission_order_with_fresh_input(settings):
    settings.CHAT_ANALYSIS_DISPATCH_LIMIT = 1
    partial = user_job("partial-needs-turn")
    message = Message.objects.get(conversation=partial.conversation)

    AnalysisJobMessage.objects.create(job=partial, message=message)
    partial.state = AnalysisJob.State.PARTIAL
    partial.specification["scheduled_message_scope"] = True
    partial.save(update_fields=("state", "specification"))
    fresh = user_job("fresh-already-served")
    fresh.state = AnalysisJob.State.READY
    fresh.save(update_fields=("state",))
    origin(
        Message.objects.get(conversation=fresh.conversation),
        fresh.created_by,
        fresh.space,
        "fresh-already-served",
        timezone.now(),
    )
    now = (timezone.now() + timedelta(hours=1)).replace(
        minute=0,
        second=0,
        microsecond=0,
    )
    with patch("chat_analysis.tasks.dispatch_analysis_job"):
        scheduled_dispatch.dispatch_due_analysis(
            now,
            now.astimezone(BEIJING).strftime("%H:%M"),
        )
    partial.refresh_from_db()
    assert partial.state == AnalysisJob.State.QUEUED
    assert AnalysisJob.objects.filter(created_by=fresh.created_by).count() == 1


def test_finished_reduction_commits_when_last_model_call_exceeds_budget(
    settings,
    monkeypatch,
):
    settings.CHAT_ANALYSIS_LLM_ENABLED = True
    settings.CHAT_ANALYSIS_AUTO_CREATE_EVENTS = True
    monkeypatch.setattr(
        execution, "_messages_for_model", lambda job, rows: rows
    )
    monkeypatch.setattr(
        execution,
        "_prepare_chunk",
        lambda job, rows: (
            {},
            [
                {
                    "title": "Case A",
                    "summary": "First incident.",
                    "source_seqs": [1],
                },
                {
                    "title": "Case B",
                    "summary": "Second incident.",
                    "source_seqs": [1],
                },
            ],
        ),
    )
    job = ready_event_batch("finished-reduction-budget")
    elapsed = [0]

    def finish(_job, candidates, *, save_progress, **kwargs):
        elapsed[0] = 2
        save_progress({"phase": 3, "groups": [[0], [1]]})
        return [[item] for item in candidates]

    with (
        patch.object(execution, "monotonic", side_effect=lambda: elapsed[0]),
        patch.object(execution, "prepare_event_reduction", side_effect=finish),
    ):
        assert execution.publish_ready_event_batches(time_limit=1) == 1
    assert Event.objects.filter(space=job.space).count() == 2
    job.refresh_from_db()
    assert "event_reduction" not in job.checkpoint
    assert "resume_after" not in job.checkpoint


@pytest.mark.parametrize("concurrency", [1, 4])
def test_hourly_publication_precedes_continuous_new_input(
    settings,
    monkeypatch,
    concurrency,
):
    settings.CHAT_ANALYSIS_LLM_ENABLED = True
    settings.CHAT_ANALYSIS_AUTO_CREATE_EVENTS = True
    settings.CHAT_ANALYSIS_MAX_CONCURRENT_USERS = concurrency
    monkeypatch.setattr(
        execution, "_messages_for_model", lambda job, rows: rows
    )
    monkeypatch.setattr(execution, "_prepare_chunk", model_results)
    old = ready_event_batch("continuous-publication")
    initial = timezone.now().replace(minute=0, second=0, microsecond=0)
    original = scheduled_dispatch._pending_origins
    monkeypatch.setattr(
        scheduled_dispatch,
        "_pending_origins",
        lambda *args, **kwargs: original(*args, **kwargs).filter(
            message__conversation__space=old.space,
        ),
    )
    dispatch_due = scheduled_dispatch.dispatch_due_analysis

    def admit_and_deliver():
        result = dispatch_due()
        # Reserve capacity before returning to the hourly tick, including
        # when the test itself is wrapped in an outer transaction.
        dispatch_pending_analysis()
        return result

    monkeypatch.setattr(
        scheduled_dispatch,
        "dispatch_due_analysis",
        admit_and_deliver,
    )
    previous = old
    for index in range(1, 4):
        now = initial + timedelta(hours=index)
        with (
            patch("django.utils.timezone.now", return_value=now),
            patch("chat_analysis.tasks.execute_analysis_job_task.delay"),
        ):
            message = add_message(old.conversation, index + 1)
            origin(
                message,
                old.created_by,
                old.space,
                f"continuous-{index}",
                now,
            )
            run_due_scheduled_analysis_task.run()
            assert not EventSuggestion.objects.filter(
                analysis_job=previous,
                status=EventSuggestion.Status.PENDING,
            ).exists()
            current = AnalysisJob.objects.get(
                created_by=old.created_by,
                state=AnalysisJob.State.QUEUED,
            )
            # Complete mapping without the task's eager publication, as if
            # this round had no time left to publish its candidates.
            previous = execution.execute_analysis_job(
                current.pk,
                worker_id=f"continuous-{index}",
            ).job
    assert execution.publish_ready_event_batches() == 1


def test_finishing_task_publishes_older_round_in_its_space(
    settings,
    monkeypatch,
):
    settings.CHAT_ANALYSIS_LLM_ENABLED = True
    settings.CHAT_ANALYSIS_AUTO_CREATE_EVENTS = True
    monkeypatch.setattr(
        execution, "_messages_for_model", lambda job, rows: rows
    )
    monkeypatch.setattr(execution, "_prepare_chunk", model_results)
    old = ready_event_batch("older-round-at-completion")
    now = timezone.now() + timedelta(hours=1)
    with (
        patch("django.utils.timezone.now", return_value=now),
        patch("chat_analysis.tasks.execute_analysis_job_task.delay"),
    ):
        message = add_message(old.conversation, 2)
        origin(message, old.created_by, old.space, "new-round", now)
        current = scheduled_dispatch.schedule_user(
            old.created_by_id,
            now,
            dispatch=False,
        )
        execute_analysis_job_task.run(current.pk, worker_id="finish-round")
    assert not EventSuggestion.objects.filter(
        analysis_job__in=(old, current),
        status=EventSuggestion.Status.PENDING,
    ).exists()


def test_publication_errors_stop_and_explicit_retry_keeps_map_results(
    settings,
    monkeypatch,
):
    settings.CHAT_ANALYSIS_LLM_ENABLED = True
    settings.CHAT_ANALYSIS_AUTO_CREATE_EVENTS = True
    monkeypatch.setattr(
        execution, "_messages_for_model", lambda job, rows: rows
    )
    with patch.object(
        execution, "_prepare_chunk", side_effect=model_results
    ) as extract:
        job = ready_event_batch("publication-failure-limit")
        initial = timezone.now()
        failures = (
            RuntimeError("endpoint unavailable"),
            execution.AnalysisBatchYield(),
            RuntimeError("endpoint unavailable"),
            RuntimeError("endpoint unavailable"),
        )
        for index, (error, expected) in enumerate(zip(failures, (1, 1, 2, 3))):
            now = initial + timedelta(hours=index)
            with (
                patch("django.utils.timezone.now", return_value=now),
                patch.object(
                    execution, "prepare_event_reduction", side_effect=error
                ) as reduce,
            ):
                assert execution.publish_ready_event_batches() == 0
                assert execution.publish_ready_event_batches() == 0
                reduce.assert_called_once()
            job.refresh_from_db()
            assert job.checkpoint["publication_failures"] == expected
            assert "endpoint unavailable" in job.error
            assert job.state == (
                AnalysisJob.State.FAILED
                if expected == 3
                else AnalysisJob.State.READY
            )
        note_ids = list(job.notes.values_list("pk", flat=True))
        job = retry_analysis_job(actor=job.created_by, job=job)
        assert "publication_failures" not in job.checkpoint
        with (
            patch.object(
                execution,
                "prepare_event_reduction",
                side_effect=lambda j, c, **kw: [[item] for item in c],
            ),
            patch("chat_analysis.tasks.execute_analysis_job_task.delay"),
        ):
            execute_analysis_job_task.run(
                job.pk, worker_id="publication-retry"
            )
        extract.assert_called_once()
    job.refresh_from_db()
    assert job.state == AnalysisJob.State.READY
    assert job.error == ""
    assert "publication_failures" not in job.checkpoint
    assert list(job.notes.values_list("pk", flat=True)) == note_ids
    assert not job.event_suggestions.filter(
        status=EventSuggestion.Status.PENDING,
    ).exists()

"""Exercise user exclusion, bounded continuation and recovery on MariaDB."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from unittest.mock import patch

import pytest
from django.contrib.auth.models import User
from django.db import close_old_connections, connections
from django.utils import timezone

from chat_analysis import execution
from chat_analysis.execution import (
    AnalysisLeaseLost,
    claim_analysis_job,
    complete_analysis_job,
    execute_analysis_job,
)
from chat_analysis.models import (
    AnalysisExecutionSlot,
    AnalysisJob,
    NoteEvidence,
)
from chat_analysis.schedule_window import BEIJING
from chat_analysis.scheduled_dispatch import dispatch_due_analysis
from chat_analysis.services import create_analysis_job, retry_analysis_job
from chat_analysis.task_status import recover_expired_analysis_jobs
from chat_analysis.tasks import execute_analysis_job_task
from chat_analysis.tests.test_execution import (
    add_message,
    make_conversation,
    make_job,
    make_space,
)
from chat_analysis.tests.test_scheduled_dispatch import origin
from chat_analysis.user_dispatch import (
    claim_publication_slot,
    dispatch_lock,
    dispatch_pending_analysis,
    publication_slot_valid,
    release_publication_slot,
)
from chat_domain.models import Message, MessageOrigin, MessagePart
from chat_ingestion.models import UploadBatch

pytestmark = pytest.mark.django_db(transaction=True)


def user_job(key, count=1):
    owner = User.objects.create_user(username=f"user-dispatch-{key}")
    space = make_space(owner, f"user-dispatch-{key}")
    conversation = make_conversation(space, f"user-dispatch-{key}")
    for seq in range(1, count + 1):
        add_message(conversation, seq)
    return make_job(space, owner, conversation, end_seq=count, key=key)


def test_user_exclusion_and_global_upper_bound(settings):
    settings.CHAT_ANALYSIS_MAX_CONCURRENT_USERS = 2
    first = user_job("first")
    conversation = make_conversation(first.space, "other-group")
    same_user = make_job(first.space, first.created_by, conversation)
    second = user_job("second")
    third = user_job("third")

    assert claim_analysis_job(first.pk, worker_id="one") is not None
    assert claim_analysis_job(same_user.pk, worker_id="two") is None
    assert claim_analysis_job(second.pk, worker_id="two") is not None
    assert claim_analysis_job(third.pk, worker_id="three") is None
    assert AnalysisExecutionSlot.objects.filter(job__isnull=False).count() == 2


def test_different_keys_reuse_the_same_frozen_input():
    job = user_job("coalesced")
    duplicate = create_analysis_job(
        actor=job.created_by,
        space=job.space,
        conversation=job.conversation,
        request_key="another-key",
        start_seq=job.start_seq,
        end_seq=job.end_seq,
        input_version=job.input_version,
    )
    assert duplicate.pk == job.pk
    assert AnalysisJob.objects.filter(space=job.space).count() == 1
    execute_analysis_job(
        job.pk, worker_id="finish", handler=lambda *a, **k: {}
    )
    replay = create_analysis_job(
        actor=job.created_by,
        space=job.space,
        conversation=job.conversation,
        request_key="another-key",
        start_seq=job.start_seq,
        end_seq=job.end_seq,
        input_version=job.input_version,
    )
    assert replay.pk == job.pk


def test_yield_preserves_progress_and_gives_another_user_a_turn(
    settings,
    monkeypatch,
):
    settings.CHAT_ANALYSIS_LLM_ENABLED = False
    settings.CHAT_ANALYSIS_MAX_CONCURRENT_USERS = 1
    settings.CHAT_ANALYSIS_BATCH_MESSAGES = 2
    monkeypatch.setattr(execution, "ANALYSIS_CHUNK_SIZE", 1)
    backlog = user_job("backlog", count=5)
    other = user_job("waiting")
    with patch("chat_analysis.tasks.execute_analysis_job_task.delay") as send:
        execute_analysis_job_task.run(backlog.pk, worker_id="first-turn")
        backlog.refresh_from_db()
        assert backlog.state == AnalysisJob.State.QUEUED
        assert backlog.checkpoint["last_ingest_seq"] == 2
        assert backlog.attempts == 0
        send.assert_called_once_with(other.pk)
        execute_analysis_job_task.run(other.pk, worker_id="other-user")
        assert send.call_args.args == (backlog.pk,)
        execute_analysis_job_task.run(backlog.pk, worker_id="second-turn")
        backlog.refresh_from_db()
        assert backlog.checkpoint["last_ingest_seq"] == 4
        assert backlog.attempts == 0
        execute_analysis_job_task.run(backlog.pk, worker_id="last-turn")
    backlog.refresh_from_db()
    assert backlog.state == AnalysisJob.State.READY
    assert backlog.attempts == 1
    assert backlog.checkpoint["messages_processed"] == 5
    assert NoteEvidence.objects.filter(note__analysis_job=backlog).count() == 5


def test_time_budget_yields_at_a_committed_chunk(settings, monkeypatch):
    settings.CHAT_ANALYSIS_LLM_ENABLED = False
    settings.CHAT_ANALYSIS_BATCH_SECONDS = 1
    monkeypatch.setattr(execution, "ANALYSIS_CHUNK_SIZE", 1)
    job = user_job("timed", count=3)
    with patch.object(execution, "monotonic", side_effect=[0, 2]):
        result = execute_analysis_job(job.pk, worker_id="timed")
    assert result.job.state == AnalysisJob.State.QUEUED
    assert result.job.checkpoint["last_ingest_seq"] == 1
    assert result.job.attempts == 0
    assert NoteEvidence.objects.filter(note__analysis_job=job).count() == 1


def test_overlapping_manual_requests_assign_each_message_once(settings):
    settings.CHAT_ANALYSIS_LLM_ENABLED = False
    first = user_job("overlap", count=6)
    first.end_seq = 4
    first.save(update_fields=("end_seq",))
    second = create_analysis_job(
        actor=first.created_by,
        space=first.space,
        conversation=first.conversation,
        request_key="overlap-tail",
        start_seq=2,
        end_seq=6,
        input_version=first.input_version,
    )
    execute_analysis_job(first.pk, worker_id="overlap-first")
    result = execute_analysis_job(second.pk, worker_id="overlap-second")
    assert result.job.state == AnalysisJob.State.READY
    assert result.job.checkpoint["messages_processed"] == 2
    assert NoteEvidence.objects.filter(note__space=first.space).count() == 6
    assert (
        Message.objects.filter(
            conversation=first.conversation,
            scheduled_analysis__isnull=False,
        ).count()
        == 6
    )


def test_duplicate_ticks_and_broker_failure_keep_one_delivery():
    job = user_job("broker")
    with patch(
        "chat_analysis.tasks.execute_analysis_job_task.delay",
        side_effect=RuntimeError("broker unavailable"),
    ):
        assert dispatch_pending_analysis() == 1
    assert AnalysisExecutionSlot.objects.get(job=job).dispatched_at is None
    with patch("chat_analysis.tasks.execute_analysis_job_task.delay") as send:
        assert dispatch_pending_analysis() == 1
        assert dispatch_pending_analysis() == 0
        send.assert_called_once_with(job.pk)


def test_large_backlog_resumes_without_duplicate_assignments(settings):
    settings.CHAT_ANALYSIS_LLM_ENABLED = False
    settings.CHAT_ANALYSIS_BATCH_MESSAGES = 250
    job = user_job("large")
    rows = Message.objects.bulk_create(
        [
            Message(
                conversation=job.conversation,
                message_key=f"large-{seq}",
                ingest_seq=seq,
                occurred_at=timezone.now(),
                sender_name="Alice",
            )
            for seq in range(2, 1202)
        ]
    )
    MessagePart.objects.bulk_create(
        [
            MessagePart(
                message=row,
                part_key="text",
                ordinal=0,
                kind=MessagePart.Kind.TEXT,
                text=f"Message {row.ingest_seq}",
            )
            for row in rows
        ]
    )
    job.end_seq = 1201
    job.save(update_fields=("end_seq",))
    for turn in range(5):
        result = execute_analysis_job(job.pk, worker_id=f"large-{turn}")
        if turn < 4:
            assert result.job.state == AnalysisJob.State.QUEUED
            assert result.job.attempts == 0
    assert result.job.state == AnalysisJob.State.READY
    assert result.job.checkpoint["messages_processed"] == 1201
    assert NoteEvidence.objects.filter(note__analysis_job=job).count() == 1201
    assert (
        job.scheduled_messages.filter(completed_at__isnull=False).count()
        == 1201
    )


def test_manual_retry_waits_behind_the_same_user(settings):
    settings.CHAT_ANALYSIS_LLM_ENABLED = False
    job = user_job("retry-gate")
    AnalysisJob.objects.filter(pk=job.pk).update(
        state=AnalysisJob.State.FAILED
    )
    conversation = make_conversation(job.space, "retry-other-group")
    other = make_job(
        job.space, job.created_by, conversation, key="retry-other"
    )
    claimed = claim_analysis_job(other.pk, worker_id="other-group")
    retry_analysis_job(actor=job.created_by, job=job)
    with patch("chat_analysis.tasks.execute_analysis_job_task.delay") as send:
        assert dispatch_pending_analysis(retry_job_id=job.pk) == 0
        complete_analysis_job(
            claimed,
            worker_id=claimed.lease_owner,
            fencing_token=claimed.fencing_token,
        )
        assert dispatch_pending_analysis() == 1
        send.assert_called_once_with(job.pk)


def test_expired_user_execution_releases_capacity_and_fences_old_writes():
    job = user_job("expired")
    other_group = make_conversation(job.space, "expiry-other-group")
    pending = make_job(job.space, job.created_by, other_group, key="pending")
    old = claim_analysis_job(job.pk, worker_id="lost")
    AnalysisJob.objects.filter(pk=job.pk).update(
        lease_until=timezone.now() - timedelta(seconds=1),
    )
    with pytest.raises(AnalysisLeaseLost):
        execution.renew_analysis_lease(
            old,
            worker_id="lost",
            fencing_token=old.fencing_token,
        )
    recover_expired_analysis_jobs()
    assert claim_analysis_job(pending.pk, worker_id="replacement") is not None
    with pytest.raises(AnalysisLeaseLost):
        complete_analysis_job(
            old,
            worker_id="lost",
            fencing_token=old.fencing_token,
            checkpoint={"last_ingest_seq": 999},
        )
    job.refresh_from_db()
    assert job.checkpoint == {}


def test_event_publication_uses_capacity_and_fences_expired_owners():
    job = user_job("publication")
    execute_analysis_job(
        job.pk, worker_id="extract", handler=lambda *a, **k: {}
    )
    old = claim_publication_slot(job.pk)
    assert old is not None
    other = user_job("publication-other")
    assert claim_analysis_job(other.pk, worker_id="other") is None
    assert claim_publication_slot(job.pk) is None
    AnalysisExecutionSlot.objects.filter(job=job).update(
        dispatched_at=timezone.now() - timedelta(seconds=301),
    )
    replacement = claim_publication_slot(job.pk)
    assert replacement is not None
    assert not publication_slot_valid(old)
    release_publication_slot(old)
    assert publication_slot_valid(replacement)
    release_publication_slot(replacement)
    assert claim_analysis_job(other.pk, worker_id="other") is not None


@pytest.mark.parametrize(
    "same_user,limit,expected",
    [(True, 2, 1), (False, 2, 2), (False, 1, 1)],
)
def test_concurrent_claims_respect_user_and_global_limits(
    settings,
    same_user,
    limit,
    expected,
):
    settings.CHAT_ANALYSIS_MAX_CONCURRENT_USERS = limit
    first = user_job("race-first")
    if same_user:
        conversation = make_conversation(first.space, "race-second-group")
        second = make_job(first.space, first.created_by, conversation)
    else:
        second = user_job("race-second")
    with dispatch_lock():
        pass
    barrier = Barrier(2)

    def claim(job_id):
        close_old_connections()
        try:
            barrier.wait(timeout=10)
            job = claim_analysis_job(job_id, worker_id=f"race-{job_id}")
            return job.pk if job else None
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(claim, (first.pk, second.pk)))
    assert sum(item is not None for item in results) == expected


def test_scheduler_bounds_users_and_keeps_one_job_per_user(settings):
    settings.CHAT_ANALYSIS_DISPATCH_LIMIT = 1
    job = user_job("scheduled-owner")
    owner, space = job.created_by, job.space
    job.delete()
    boundary = timezone.now() + timedelta(seconds=2)
    before = boundary - timedelta(seconds=1)
    for index in range(3):
        conversation = make_conversation(space, f"scheduled-group-{index}")
        message = add_message(conversation, 1)
        origin(message, owner, space, f"scheduled-origin-{index}", before)
    now = boundary
    boundary = boundary.astimezone(BEIJING).replace(second=0, microsecond=0)
    Message.objects.filter(conversation__space=space).update(
        created_at=boundary - timedelta(seconds=2),
    )
    MessageOrigin.objects.filter(message__conversation__space=space).update(
        created_at=boundary - timedelta(seconds=2),
    )
    UploadBatch.objects.filter(space=space).update(
        completed_at=boundary - timedelta(seconds=2),
    )
    schedule = boundary.strftime("%H:%M")
    with patch("chat_analysis.tasks.dispatch_analysis_job") as dispatch:
        assert dispatch_due_analysis(now, schedule)["jobs"] == 1
        assert dispatch_due_analysis(now, schedule)["jobs"] == 0
    assert AnalysisJob.objects.filter(created_by=owner).count() == 1
    dispatch.assert_called_once()


def test_queue_wait_includes_latest_input_and_running_batch_stays_frozen(
    settings,
    monkeypatch,
):
    settings.CHAT_ANALYSIS_LLM_ENABLED = True
    settings.CHAT_ANALYSIS_AUTO_CREATE_EVENTS = False
    settings.CHAT_ANALYSIS_BATCH_MESSAGES = 2
    monkeypatch.setattr(
        execution, "_messages_for_model", lambda job, rows: rows
    )
    job = user_job("round-owner")
    owner, space, conversation = job.created_by, job.space, job.conversation
    job.delete()
    boundary = (
        timezone.now()
        .astimezone(BEIJING)
        .replace(
            minute=0,
            second=0,
            microsecond=0,
        )
    )
    old = Message.objects.get(conversation=conversation)
    origin(old, owner, space, "round-old", boundary)
    Message.objects.filter(pk=old.pk).update(created_at=boundary)
    MessageOrigin.objects.filter(message=old).update(created_at=boundary)
    during_execution = []

    def model(_job, _messages):
        if not during_execution:
            message = add_message(conversation, 3)
            origin(message, owner, space, "round-during", timezone.now())
            during_execution.append(message)
        return {}, []

    monkeypatch.setattr(execution, "_prepare_chunk", model)
    with patch("chat_analysis.tasks.execute_analysis_job_task.delay") as send:
        dispatch_due_analysis(boundary, boundary.strftime("%H:%M"))
        first_id = send.call_args.args[0]
        first = AnalysisJob.objects.get(pk=first_id)
        assert first.end_seq == 0
        assert first.specification["snapshot_pending"] is True
        assert first.scheduled_messages.count() == 0

        # This history arrives after queueing but before the user's turn.
        queued_upload = add_message(
            conversation,
            2,
            occurred_at=boundary - timedelta(days=400),
        )
        origin(
            queued_upload, owner, space, "round-while-waiting", timezone.now()
        )
        execute_analysis_job_task.run(first_id, worker_id="round-first")
        first.refresh_from_db()
        assert first.end_seq == 2
        assert first.checkpoint["messages_processed"] == 2
        assert first.specification["snapshot_pending"] is False
        assert first.scheduled_messages.filter(message=queued_upload).exists()
        assert not hasattr(during_execution[0], "scheduled_analysis")

        # A continuation freezes fresh input without another hourly wait.
        second_id = send.call_args.args[0]
        assert second_id != first_id
        execute_analysis_job_task.run(second_id, worker_id="round-second")
        second = AnalysisJob.objects.get(pk=second_id)
        assert second.state == AnalysisJob.State.READY
        assert second.end_seq == 3
        assert second.checkpoint["messages_processed"] == 1
    assert AnalysisJob.objects.filter(space=space).count() == 2
    assert NoteEvidence.objects.filter(note__space=space).count() == 3

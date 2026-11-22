"""Regression coverage for batch admission, upgrades and hourly recovery."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from importlib import import_module
from io import StringIO
from threading import Event
from unittest.mock import patch

import pytest
from django.apps import apps
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import close_old_connections, connections
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate

from chat_analysis import execution, services, views
from chat_analysis.models import AnalysisJob, AnalysisJobMessage, NoteEvidence
from chat_analysis.scheduled_dispatch import schedule_user
from chat_analysis.services import (
    add_note_evidence,
    cancel_analysis_job,
    create_analysis_job,
    create_note,
    retry_analysis_job,
)
from chat_analysis.task_status import recover_expired_analysis_jobs
from chat_analysis.tasks import (
    execute_analysis_job_task,
    sweep_stale_async_tasks,
)
from chat_analysis.tests.test_execution import add_message, make_conversation
from chat_analysis.tests.test_scheduled_dispatch import origin
from chat_analysis.tests.test_user_dispatch import user_job
from chat_analysis.user_dispatch import (
    dispatch_lock,
    dispatch_pending_analysis,
    lock_dispatch_row,
)
from chat_domain.models import Conversation, Message, MessagePart
from chat_ingestion.models import UploadBatch
from spaces.models import SpaceWorkflowConfig

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.mark.parametrize("blocked", ["direct", "unknown", None, " \n\u3000"])
def test_ineligible_head_does_not_block_readable_group(blocked):
    base = user_job("ineligible")
    owner, space, conversation = base.created_by, base.space, base.conversation
    base.delete()
    config, _ = SpaceWorkflowConfig.objects.get_or_create(space=space)
    config.chat_analysis_preferences = {"conversation_types": ["group"]}
    config.save()
    if blocked in ("direct", "unknown"):
        conversation.kind = blocked
        conversation.save(update_fields=("kind",))
    else:
        MessagePart.objects.filter(message__conversation=conversation).update(
            text=blocked or "",
        )
    origin(
        Message.objects.get(conversation=conversation),
        owner,
        space,
        "excluded",
        timezone.now(),
    )
    allowed = make_conversation(space, "allowed")
    allowed.kind = Conversation.Kind.GROUP
    allowed.save(update_fields=("kind",))
    row = add_message(allowed, 1)
    origin(row, owner, space, "allowed", timezone.now())
    job = schedule_user(owner.pk, timezone.now(), dispatch=False)
    assert job is not None
    assert job.conversation_id == allowed.pk


def test_unreadable_partial_does_not_block_new_input():
    base = user_job("unreadable")
    base.state = AnalysisJob.State.PARTIAL
    base.save(update_fields=("state",))
    row = Message.objects.get(conversation=base.conversation)
    MessagePart.objects.filter(message=row).delete()
    AnalysisJobMessage.objects.create(job=base, message=row)
    conversation = make_conversation(base.space, "readable")
    origin(
        add_message(conversation, 1),
        base.created_by,
        base.space,
        "readable",
        timezone.now(),
    )
    job = schedule_user(base.created_by_id, timezone.now(), dispatch=False)
    assert job.pk != base.pk
    assert job.conversation_id == conversation.pk
    base.refresh_from_db()
    assert base.state == AnalysisJob.State.PARTIAL


def test_legacy_running_job_without_slot_counts_until_recovered(settings):
    settings.CHAT_ANALYSIS_MAX_CONCURRENT_USERS = 1
    old = user_job("legacy-running")
    other = user_job("upgrade-other")
    AnalysisJob.objects.filter(pk=old.pk).update(
        state=AnalysisJob.State.RUNNING,
        lease_owner="old-worker",
        lease_until=timezone.now() + timedelta(minutes=1),
        attempts=1,
        fencing_token=1,
        checkpoint={"last_ingest_seq": 0},
    )
    assert execution.claim_analysis_job(other.pk, worker_id="new") is None
    settings.CHAT_ANALYSIS_MAX_CONCURRENT_USERS = 2
    conversation = make_conversation(old.space, "same-owner")
    same = create_analysis_job(
        actor=old.created_by,
        space=old.space,
        conversation=conversation,
        request_key="same-owner",
        start_seq=0,
        end_seq=1,
        input_version="v1",
    )
    assert execution.claim_analysis_job(same.pk, worker_id="new") is None
    claimed = execution.claim_analysis_job(other.pk, worker_id="other")
    assert claimed is not None
    AnalysisJob.objects.filter(pk=old.pk).update(
        lease_until=timezone.now() - timedelta(seconds=1),
    )
    assert execution.claim_analysis_job(same.pk, worker_id="new") is None
    assert recover_expired_analysis_jobs()["requeued"] == 1
    recovered = execution.claim_analysis_job(old.pk, worker_id="recovered")
    assert recovered.checkpoint == {"last_ingest_seq": 0}
    assert recovered.fencing_token > 1


def test_cancelled_incomplete_assignments_can_be_requested_again(settings):
    settings.CHAT_ANALYSIS_LLM_ENABLED = False
    old = user_job("cancelled", count=2)
    first, second = Message.objects.filter(
        conversation=old.conversation,
    ).order_by("ingest_seq")
    AnalysisJobMessage.objects.create(
        job=old,
        message=first,
        completed_at=timezone.now(),
    )
    AnalysisJobMessage.objects.create(job=old, message=second)
    for message in (first, second):
        note = create_note(
            actor=old.created_by,
            space=old.space,
            note_key=f"cancelled-{message.pk}",
            title="old fragment",
            content="old fragment",
            analysis_job=old,
        )
        add_note_evidence(actor=old.created_by, note=note, message=message)
    cancel_analysis_job(actor=old.created_by, job=old)
    fresh = create_analysis_job(
        actor=old.created_by,
        space=old.space,
        conversation=old.conversation,
        request_key="fresh",
        start_seq=0,
        end_seq=2,
        input_version="wechat.v1",
    )
    result = execution.execute_analysis_job(fresh.pk, worker_id="fresh")
    assert result.job.state == AnalysisJob.State.READY
    assert result.job.checkpoint["messages_processed"] == 1
    assert AnalysisJobMessage.objects.get(message=first).job_id == old.pk
    assert AnalysisJobMessage.objects.get(message=second).job_id == fresh.pk
    assert NoteEvidence.objects.filter(note__analysis_job=fresh).count() == 1
    assert execution.execute_analysis_job(old.pk, worker_id="stale") is None


def test_hourly_gate_blocks_duplicate_delivery_but_explicit_retry_is_immediate(
    settings,
):
    settings.CHAT_ANALYSIS_LLM_ENABLED = False
    settings.CHAT_ANALYSIS_BATCH_MESSAGES = 1
    job = user_job("hourly", count=2)
    result = execution.execute_analysis_job(job.pk, worker_id="first")
    assert result.job.state == AnalysisJob.State.QUEUED
    with patch("chat_analysis.tasks.execute_analysis_job_task.delay") as send:
        assert dispatch_pending_analysis() == 0
        send.assert_not_called()
    assert (
        execution.execute_analysis_job(job.pk, worker_id="duplicate") is None
    )
    due = datetime.fromisoformat(result.job.checkpoint["resume_after"])
    with patch("django.utils.timezone.now", return_value=due):
        result = execution.execute_analysis_job(job.pk, worker_id="next-hour")
    assert result.job.state == AnalysisJob.State.READY
    assert NoteEvidence.objects.filter(note__analysis_job=job).count() == 2
    job.state = AnalysisJob.State.FAILED
    job.checkpoint = {"resume_after": due.isoformat()}
    job.save(update_fields=("state", "checkpoint"))
    retried = retry_analysis_job(actor=job.created_by, job=job)
    assert "resume_after" not in retried.checkpoint


def test_completed_batch_boundary_is_shared_across_groups(
    settings, monkeypatch
):
    settings.CHAT_ANALYSIS_LLM_ENABLED = True
    settings.CHAT_ANALYSIS_AUTO_CREATE_EVENTS = False
    settings.CHAT_ANALYSIS_BATCH_MESSAGES = 10
    monkeypatch.setattr(
        execution, "_messages_for_model", lambda job, rows: rows
    )
    base = user_job("batch-boundary")
    owner, space, conversation = base.created_by, base.space, base.conversation
    base.delete()
    row = Message.objects.get(conversation=conversation)
    origin(row, owner, space, "completed", timezone.now())
    # An overlapping upload does not invalidate the completed origin.
    origin(
        row,
        owner,
        space,
        "duplicate-upload",
        None,
        UploadBatch.Status.PROCESSING,
    )
    another = make_conversation(space, "second-group")
    origin(
        add_message(another, 1),
        owner,
        space,
        "second-completed",
        timezone.now(),
    )
    late = add_message(another, 2)
    batch = origin(
        late,
        owner,
        space,
        "still-uploading",
        None,
        UploadBatch.Status.PROCESSING,
    )
    job = schedule_user(owner.pk, timezone.now(), dispatch=False)

    def complete_during_analysis(_job, _messages):
        UploadBatch.objects.filter(pk=batch.pk).update(
            status=UploadBatch.Status.COMPLETED,
            completed_at=timezone.now(),
        )
        return {}, []

    monkeypatch.setattr(execution, "_prepare_chunk", complete_during_analysis)
    with patch("chat_analysis.tasks.execute_analysis_job_task.delay") as send:
        execute_analysis_job_task.run(job.pk, worker_id="batch")
        send.assert_not_called()
    assert NoteEvidence.objects.filter(note__space=space).count() == 2
    assert not AnalysisJobMessage.objects.filter(message=late).exists()
    next_job = schedule_user(owner.pk, timezone.now(), dispatch=False)
    execution.execute_analysis_job(next_job.pk, worker_id="later")
    assert (
        AnalysisJobMessage.objects.get(message=late).completed_at is not None
    )
    assert AnalysisJobMessage.objects.filter(message=row).count() == 1


def test_non_event_sweeper_leaves_event_recovery_to_hourly_tick():
    job = user_job("no-five-minute")
    AnalysisJob.objects.filter(pk=job.pk).update(
        state=AnalysisJob.State.RUNNING,
        attempts=1,
        lease_until=timezone.now() - timedelta(seconds=5),
    )
    with patch("chat_analysis.tasks.execute_analysis_job_task.delay") as send:
        result = sweep_stale_async_tasks.run()
    send.assert_not_called()
    assert result["jobs_requeued"] == 0
    job.refresh_from_db()
    assert job.state == AnalysisJob.State.RUNNING


def test_rollback_guard_rejects_unfrozen_or_running_jobs():
    job = user_job("rollback")
    job.specification["snapshot_pending"] = True
    job.save(update_fields=("specification",))
    with pytest.raises(CommandError, match="frozen"):
        call_command("check_analysis_handoff", stdout=StringIO())
    job.specification["snapshot_pending"] = False
    job.state = AnalysisJob.State.RUNNING
    job.save(update_fields=("specification", "state"))
    with pytest.raises(CommandError, match="Running"):
        call_command("check_analysis_handoff", stdout=StringIO())
    job.state = AnalysisJob.State.READY
    job.specification["snapshot_pending"] = True
    job.save(update_fields=("state", "specification"))
    call_command("check_analysis_handoff", stdout=StringIO())


def test_existing_tick_moves_to_hourly_preserving_disabled_and_custom():
    from django_celery_beat.models import CrontabSchedule, PeriodicTask

    migration = import_module(
        "chat_analysis.migrations.0010_hourly_analysis_schedule",
    )
    old = CrontabSchedule.objects.create(minute="*/5")
    task, _ = PeriodicTask.objects.update_or_create(
        name="chat-analysis-run-due-scheduled-analysis",
        defaults={
            "task": "chat_analysis.tasks.run_due_scheduled_analysis_task",
            "crontab": old,
            "enabled": False,
        },
    )
    with connections["default"].schema_editor() as schema_editor:
        migration.use_hourly_tick(apps, schema_editor)
    task.refresh_from_db()
    assert task.crontab.minute == "0"
    assert task.enabled is False
    old.refresh_from_db()
    assert old.minute == "*/5"
    custom = CrontabSchedule.objects.create(minute="15")
    task.crontab = custom
    task.save()
    with connections["default"].schema_editor() as schema_editor:
        migration.use_hourly_tick(apps, schema_editor)
    task.refresh_from_db()
    assert task.crontab_id == custom.pk


@pytest.mark.parametrize("retry", [False, True])
def test_http_cancel_retry_and_worker_acquire_locks_in_the_same_order(retry):
    job = user_job("http-lock-order")
    if retry:
        AnalysisJob.objects.filter(pk=job.pk).update(
            state=AnalysisJob.State.FAILED
        )
    with dispatch_lock():
        pass
    worker_holds_lock, api_wants_lock = Event(), Event()

    def observed_lock():
        api_wants_lock.set()
        lock_dispatch_row()

    def worker():
        close_old_connections()
        try:
            with dispatch_lock():
                worker_holds_lock.set()
                assert api_wants_lock.wait(10)
                return execution.claim_analysis_job(job.pk, worker_id="race")
        finally:
            connections.close_all()

    def api():
        close_old_connections()
        try:
            assert worker_holds_lock.wait(10)
            request = APIRequestFactory().post("/", {}, format="json")
            force_authenticate(request, user=job.created_by)
            view = (
                views.AnalysisJobRetryAPIView
                if retry
                else views.AnalysisJobCancelAPIView
            )
            response = view.as_view()(request, job_id=job.pk)
            return response.status_code
        finally:
            connections.close_all()

    with (
        patch.object(views, "lock_dispatch_row", side_effect=observed_lock),
        patch.object(services, "lock_dispatch_row", side_effect=observed_lock),
        patch.object(views, "dispatch_analysis_job"),
        ThreadPoolExecutor(max_workers=2) as pool,
    ):
        running = pool.submit(worker)
        response = pool.submit(api)
        running.result(timeout=20)
        assert response.result(timeout=20) == (202 if retry else 200)


def test_repaired_text_rewinds_partial_cursor_without_replaying_completed(
    settings,
    monkeypatch,
):
    settings.CHAT_ANALYSIS_LLM_ENABLED = True
    settings.CHAT_ANALYSIS_AUTO_CREATE_EVENTS = False
    job = user_job("repaired-text", count=2)
    first, second = Message.objects.filter(
        conversation=job.conversation,
    ).order_by("ingest_seq")
    AnalysisJobMessage.objects.create(job=job, message=first)
    AnalysisJobMessage.objects.create(
        job=job,
        message=second,
        completed_at=timezone.now(),
    )
    job.specification["scheduled_message_scope"] = True
    job.state = AnalysisJob.State.PARTIAL
    job.checkpoint = {
        "last_ingest_seq": 2,
        "messages_processed": 1,
        "partial": True,
    }
    job.save(update_fields=("state", "checkpoint", "specification"))
    monkeypatch.setattr(
        execution, "_messages_for_model", lambda job, rows: rows
    )
    seen = []

    def extract(_job, rows):
        seen.extend(row.pk for row in rows)
        return {}, []

    monkeypatch.setattr(execution, "_prepare_chunk", extract)
    resumed = schedule_user(job.created_by_id, timezone.now(), dispatch=False)
    assert resumed.pk == job.pk
    result = execution.execute_analysis_job(job.pk, worker_id="repaired")
    assert result.job.state == AnalysisJob.State.READY
    assert result.job.checkpoint["messages_processed"] == 2
    assert seen == [first.pk]
    assert (
        job.scheduled_messages.filter(completed_at__isnull=False).count() == 2
    )


@pytest.mark.parametrize("yielded", [False, True])
def test_publication_failure_or_budget_waits_until_next_hour(
    settings,
    monkeypatch,
    yielded,
):
    settings.CHAT_ANALYSIS_LLM_ENABLED = True
    settings.CHAT_ANALYSIS_AUTO_CREATE_EVENTS = True
    job = user_job("publication-retry")
    job.specification.update(
        {
            "scheduled_message_scope": True,
            "boundary": timezone.now().isoformat(),
        }
    )
    job.save(update_fields=("specification",))
    AnalysisJobMessage.objects.create(
        job=job,
        message=Message.objects.get(conversation=job.conversation),
    )
    monkeypatch.setattr(
        execution, "_messages_for_model", lambda job, rows: rows
    )
    monkeypatch.setattr(
        execution,
        "_prepare_chunk",
        lambda *_: (
            {},
            [
                {
                    "title": "Case ABC",
                    "summary": "Alice reported Case ABC.",
                    "source_seqs": [1],
                }
            ],
        ),
    )
    result = execution.execute_analysis_job(job.pk, worker_id="extract")
    assert result.job.state == AnalysisJob.State.READY
    failure = (
        execution.AnalysisBatchYield() if yielded else RuntimeError("LLM")
    )
    with patch.object(
        execution,
        "prepare_event_reduction",
        side_effect=failure,
    ) as reduce:
        assert execution.publish_ready_event_batches() == 0
        assert execution.publish_ready_event_batches() == 0
        reduce.assert_called_once()
    job.refresh_from_db()
    due = datetime.fromisoformat(job.checkpoint["resume_after"])
    with (
        patch("django.utils.timezone.now", return_value=due),
        patch.object(
            execution,
            "prepare_event_reduction",
            side_effect=lambda job, candidates, **kw: [candidates],
        ),
    ):
        assert execution.publish_ready_event_batches() == 1

from datetime import timedelta

import pytest
from django.contrib.auth.models import User
from django.utils import timezone

from chat_analysis import execution
from chat_analysis.execution import (
    AnalysisLeaseLost,
    claim_analysis_job,
    complete_analysis_job,
    execute_analysis_job,
    update_analysis_checkpoint,
)
from chat_analysis.models import AnalysisJob, Note, NoteEvidence
from chat_analysis.services import (
    ChatAnalysisPermissionError,
    create_analysis_job,
    create_note,
)
from chat_analysis.tasks import execute_analysis_job_task
from chat_domain.models import Conversation, Message, MessagePart
from spaces.models import Space, SpaceMembership

pytestmark = [pytest.mark.django_db, pytest.mark.integration]


def make_space(owner, slug="execution-team"):
    space = Space.objects.create(
        name=slug,
        slug=slug,
        kind=Space.Kind.TEAM,
        owner=owner,
    )
    SpaceMembership.objects.create(
        space=space,
        user=owner,
        role=SpaceMembership.Role.OWNER,
    )
    return space


def make_conversation(space, key="group-a"):
    return Conversation.objects.create(
        space=space,
        platform=Conversation.Platform.WECHAT,
        source_namespace="local-account",
        source_conversation_id=key,
        identity_key=f"wechat:local-account:{key}",
        title=key,
    )


def add_message(conversation, index, text="hello", occurred_at=None):
    message = Message.objects.create(
        conversation=conversation,
        message_key=f"m-{index}",
        ingest_seq=index,
        occurred_at=occurred_at or timezone.now(),
        sender_name="Alice",
    )
    if text is not None:
        MessagePart.objects.create(
            message=message,
            part_key="p1",
            kind=MessagePart.Kind.TEXT,
            ordinal=0,
            text=text,
        )
    return message


def make_job(space, owner, conversation, end_seq=3, key="job-1"):
    return create_analysis_job(
        actor=owner,
        space=space,
        conversation=conversation,
        request_key=key,
        start_seq=0,
        end_seq=end_seq,
        input_version="wechat.v1",
    )


def test_claim_is_exclusive_and_increments_fence():
    owner = User.objects.create_user(username="exec-owner-1")
    space = make_space(owner)
    conversation = make_conversation(space)
    job = make_job(space, owner, conversation)

    first = claim_analysis_job(job.pk, worker_id="worker-1")
    second = claim_analysis_job(job.pk, worker_id="worker-2")

    assert first.state == AnalysisJob.State.RUNNING
    assert first.attempts == 1
    assert first.fencing_token == 1
    assert first.lease_owner == "worker-1"
    assert first.lease_until is not None
    assert second is None


def test_expired_lease_is_reclaimed_and_old_worker_is_fenced():
    owner = User.objects.create_user(username="exec-owner-2")
    space = make_space(owner)
    conversation = make_conversation(space)
    job = make_job(space, owner, conversation)

    first = claim_analysis_job(job.pk, worker_id="worker-1")
    AnalysisJob.objects.filter(pk=job.pk).update(
        lease_until=timezone.now() - timedelta(seconds=1)
    )
    second = claim_analysis_job(job.pk, worker_id="worker-2")

    assert second.fencing_token == first.fencing_token + 1
    assert second.attempts == 2

    with pytest.raises(AnalysisLeaseLost):
        complete_analysis_job(
            first,
            worker_id="worker-1",
            fencing_token=first.fencing_token,
        )
    with pytest.raises(AnalysisLeaseLost):
        update_analysis_checkpoint(
            first,
            worker_id="worker-1",
            fencing_token=first.fencing_token,
            checkpoint={"last_ingest_seq": 1},
        )


def test_execution_writes_chunked_notes_with_evidence(monkeypatch):
    monkeypatch.setattr(execution, "ANALYSIS_CHUNK_SIZE", 2)
    owner = User.objects.create_user(username="exec-owner-3")
    space = make_space(owner)
    conversation = make_conversation(space)
    now = timezone.now()
    add_message(conversation, 1, "first", occurred_at=now)
    add_message(conversation, 2, "second", occurred_at=now)
    add_message(conversation, 3, "third", occurred_at=now)
    job = make_job(space, owner, conversation)

    result = execute_analysis_job(job.pk, worker_id="worker-1")
    job.refresh_from_db()

    assert result.job.pk == job.pk
    assert job.state == AnalysisJob.State.READY
    assert job.lease_owner == ""
    assert job.lease_until is None
    assert job.checkpoint["last_ingest_seq"] == 3
    assert job.checkpoint["messages_processed"] == 3
    assert job.checkpoint["notes_written"] == 2
    assert job.result_ref == {
        "messages_processed": 3,
        "notes_written": 2,
        "last_ingest_seq": 3,
    }
    notes = Note.objects.filter(analysis_job=job).order_by("note_key")
    assert notes.count() == 2
    assert list(notes.values_list("note_key", flat=True)) == [
        f"job:{job.uuid}:1-2",
        f"job:{job.uuid}:3-3",
    ]
    assert notes[0].origin == Note.Origin.AUTO
    assert notes[0].start_at == now
    assert NoteEvidence.objects.filter(note=notes[0]).count() == 2
    assert NoteEvidence.objects.filter(note=notes[1]).count() == 1


def test_repeated_execution_does_not_duplicate_notes_or_evidence(monkeypatch):
    monkeypatch.setattr(execution, "ANALYSIS_CHUNK_SIZE", 2)
    owner = User.objects.create_user(username="exec-owner-4")
    space = make_space(owner)
    conversation = make_conversation(space)
    for index in (1, 2, 3):
        add_message(conversation, index, f"message {index}")
    job = make_job(space, owner, conversation)

    execute_analysis_job(job.pk, worker_id="worker-1")
    AnalysisJob.objects.filter(pk=job.pk).update(
        state=AnalysisJob.State.QUEUED,
        lease_owner="",
        lease_until=None,
    )
    execute_analysis_job(job.pk, worker_id="worker-2")
    job.refresh_from_db()

    assert job.state == AnalysisJob.State.READY
    assert job.attempts == 2
    assert Note.objects.filter(analysis_job=job).count() == 2
    assert NoteEvidence.objects.filter(
        note__analysis_job=job
    ).count() == 3


def test_manual_note_with_the_same_key_is_not_overwritten(monkeypatch):
    monkeypatch.setattr(execution, "ANALYSIS_CHUNK_SIZE", 1)
    owner = User.objects.create_user(username="exec-owner-5")
    space = make_space(owner)
    conversation = make_conversation(space)
    add_message(conversation, 1, "first")
    add_message(conversation, 2, "second")
    job = make_job(space, owner, conversation, end_seq=2)
    manual = create_note(
        actor=owner,
        space=space,
        note_key=f"job:{job.uuid}:1-1",
        title="Manual note",
        content="Confirmed by a human.",
        origin=Note.Origin.MANUAL,
    )

    execute_analysis_job(job.pk, worker_id="worker-1")

    manual.refresh_from_db()
    assert manual.title == "Manual note"
    assert manual.content == "Confirmed by a human."
    assert manual.origin == Note.Origin.MANUAL
    assert NoteEvidence.objects.filter(note=manual).count() == 0
    assert Note.objects.filter(space=space).count() == 2
    assert Note.objects.filter(analysis_job=job).count() == 1


def test_messages_without_text_mark_the_job_partial():
    owner = User.objects.create_user(username="exec-owner-6")
    space = make_space(owner)
    conversation = make_conversation(space)
    add_message(conversation, 1, "readable")
    add_message(conversation, 2, text=None)
    job = make_job(space, owner, conversation, end_seq=2)

    execute_analysis_job(job.pk, worker_id="worker-1")
    job.refresh_from_db()

    assert job.state == AnalysisJob.State.PARTIAL
    assert job.checkpoint["partial"] is True
    assert job.result_ref["notes_written"] == 1
    assert Note.objects.filter(analysis_job=job).count() == 1


def test_retryable_failure_requeues_until_max_attempts():
    owner = User.objects.create_user(username="exec-owner-7")
    space = make_space(owner)
    conversation = make_conversation(space)
    job = make_job(space, owner, conversation)

    def boom(job, *, lease_seconds):
        raise RuntimeError("temporary outage")

    first = execute_analysis_job(
        job.pk,
        worker_id="worker-1",
        handler=boom,
        max_attempts=2,
    )
    assert first.job.state == AnalysisJob.State.QUEUED
    assert first.job.attempts == 1
    assert "RuntimeError" in first.job.error
    assert first.job.lease_owner == ""

    second = execute_analysis_job(
        job.pk,
        worker_id="worker-1",
        handler=boom,
        max_attempts=2,
    )
    assert second.job.state == AnalysisJob.State.FAILED
    assert second.job.attempts == 2
    assert execute_analysis_job(job.pk, worker_id="worker-1") is None


def test_permission_failure_is_not_retried():
    owner = User.objects.create_user(username="exec-owner-8")
    space = make_space(owner)
    conversation = make_conversation(space)
    job = make_job(space, owner, conversation)

    def denied(job, *, lease_seconds):
        raise ChatAnalysisPermissionError("membership removed")

    result = execute_analysis_job(
        job.pk,
        worker_id="worker-1",
        handler=denied,
        max_attempts=5,
    )

    assert result.job.state == AnalysisJob.State.FAILED
    assert result.job.attempts == 1


def test_archived_space_marks_the_job_failed():
    owner = User.objects.create_user(username="exec-owner-9")
    space = make_space(owner)
    conversation = make_conversation(space)
    job = make_job(space, owner, conversation)
    Space.objects.filter(pk=space.pk).update(status=Space.Status.ARCHIVED)

    result = execute_analysis_job(job.pk, worker_id="worker-1")

    assert result.job.state == AnalysisJob.State.FAILED
    assert "Space is not active" in result.job.error


def test_celery_task_runs_the_job():
    owner = User.objects.create_user(username="exec-owner-10")
    space = make_space(owner)
    conversation = make_conversation(space)
    add_message(conversation, 1, "task input")
    job = make_job(space, owner, conversation, end_seq=1)

    payload = execute_analysis_job_task.run(job.pk, worker_id="celery-test")
    job.refresh_from_db()

    assert payload == {
        "job_id": job.pk,
        "state": AnalysisJob.State.READY,
        "claimed": True,
    }
    assert Note.objects.filter(analysis_job=job).count() == 1

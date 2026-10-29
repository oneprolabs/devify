"""Analysis job execution: leases, fencing, checkpoints and rule extraction.

Execution never trusts a worker beyond its lease. Every claim increments the
job's fencing token, so a worker whose lease expired cannot complete or
overwrite a job that another worker has taken over.

The first extractor is deliberately rule based: it turns a message window
into chunked Notes with message evidence. Automatic runs reuse stable note
keys and the existing Note service, which refuses to overwrite manual Notes.
"""

from dataclasses import dataclass
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from chat_analysis.models import AnalysisJob, Note
from chat_analysis.services import (
    ChatAnalysisError,
    ChatAnalysisPermissionError,
    add_note_evidence,
    create_note,
)
from chat_domain.models import Message, MessagePart
from spaces.models import Space
from spaces.services import SpacePermissionService

DEFAULT_LEASE_SECONDS = 300
DEFAULT_MAX_ATTEMPTS = 3
ANALYSIS_CHUNK_SIZE = 200


class AnalysisJobRejected(Exception):
    """Raised when a job may not run for a non-transient reason."""


class AnalysisLeaseLost(Exception):
    """Raised when a worker no longer holds the job lease."""


@dataclass(frozen=True)
class ExecutionResult:
    job: AnalysisJob
    handler_result: dict


def _lock_job(job_id):
    return (
        AnalysisJob.objects.select_for_update()
        .filter(pk=job_id)
        .first()
    )


def _ensure_lease(job, worker_id, fencing_token):
    if (
        job.state != AnalysisJob.State.RUNNING
        or job.lease_owner != worker_id
        or job.fencing_token != fencing_token
    ):
        raise AnalysisLeaseLost(
            "The analysis job lease is no longer held by this worker."
        )


def claim_analysis_job(
    job_id,
    *,
    worker_id,
    lease_seconds=DEFAULT_LEASE_SECONDS,
):
    """Claim a queued job or an expired running job.

    Returns ``None`` when another worker holds a live lease or the job is in
    a terminal state. Each successful claim increments ``fencing_token`` and
    ``attempts``.
    """
    if not worker_id:
        raise ValueError("worker_id is required.")
    now = timezone.now()
    with transaction.atomic():
        job = _lock_job(job_id)
        if job is None:
            return None
        if job.state == AnalysisJob.State.RUNNING:
            if job.lease_until and job.lease_until > now:
                return None
        elif job.state != AnalysisJob.State.QUEUED:
            return None
        job.state = AnalysisJob.State.RUNNING
        job.lease_owner = worker_id
        job.lease_until = now + timedelta(seconds=lease_seconds)
        job.fencing_token = job.fencing_token + 1
        job.attempts = job.attempts + 1
        job.error = ""
        job.save(
            update_fields=(
                "state",
                "lease_owner",
                "lease_until",
                "fencing_token",
                "attempts",
                "error",
                "updated_at",
            )
        )
        return job


def renew_analysis_lease(
    job,
    *,
    worker_id,
    fencing_token,
    lease_seconds=DEFAULT_LEASE_SECONDS,
    checkpoint=None,
):
    """Extend the lease and optionally store a checkpoint."""
    with transaction.atomic():
        locked = AnalysisJob.objects.select_for_update().get(pk=job.pk)
        _ensure_lease(locked, worker_id, fencing_token)
        locked.lease_until = timezone.now() + timedelta(
            seconds=lease_seconds
        )
        update_fields = ["lease_until", "updated_at"]
        if checkpoint is not None:
            locked.checkpoint = checkpoint
            update_fields.append("checkpoint")
        locked.save(update_fields=update_fields)
        return locked


def update_analysis_checkpoint(
    job,
    *,
    worker_id,
    fencing_token,
    checkpoint,
):
    return renew_analysis_lease(
        job,
        worker_id=worker_id,
        fencing_token=fencing_token,
        checkpoint=checkpoint,
    )


def complete_analysis_job(
    job,
    *,
    worker_id,
    fencing_token,
    checkpoint=None,
    result_ref=None,
    partial=False,
):
    """Finish a job as ``ready`` or, with unreadable input, ``partial``."""
    with transaction.atomic():
        locked = AnalysisJob.objects.select_for_update().get(pk=job.pk)
        _ensure_lease(locked, worker_id, fencing_token)
        locked.state = (
            AnalysisJob.State.PARTIAL
            if partial
            else AnalysisJob.State.READY
        )
        if checkpoint is not None:
            locked.checkpoint = checkpoint
        if result_ref is not None:
            locked.result_ref = result_ref
        locked.lease_owner = ""
        locked.lease_until = None
        locked.error = ""
        locked.save(
            update_fields=(
                "state",
                "checkpoint",
                "result_ref",
                "lease_owner",
                "lease_until",
                "error",
                "updated_at",
            )
        )
        return locked


def fail_analysis_job(
    job,
    *,
    worker_id,
    fencing_token,
    error,
    retryable=False,
    max_attempts=DEFAULT_MAX_ATTEMPTS,
    checkpoint=None,
):
    """Record a failure and requeue it while attempts remain."""
    with transaction.atomic():
        locked = AnalysisJob.objects.select_for_update().get(pk=job.pk)
        _ensure_lease(locked, worker_id, fencing_token)
        locked.error = str(error)[:4000]
        if checkpoint is not None:
            locked.checkpoint = checkpoint
        locked.lease_owner = ""
        locked.lease_until = None
        if retryable and locked.attempts < max_attempts:
            locked.state = AnalysisJob.State.QUEUED
        else:
            locked.state = AnalysisJob.State.FAILED
        locked.save(
            update_fields=(
                "state",
                "error",
                "checkpoint",
                "lease_owner",
                "lease_until",
                "updated_at",
            )
        )
        return locked


def execute_analysis_job(
    job_id,
    *,
    worker_id,
    handler=None,
    lease_seconds=DEFAULT_LEASE_SECONDS,
    max_attempts=DEFAULT_MAX_ATTEMPTS,
):
    """Claim and run one job, recording success, retry or failure.

    ``handler`` receives the claimed job and a ``lease_seconds`` keyword. It
    must return a dict with optional ``checkpoint``, ``partial`` and
    ``result_ref`` keys. A handler that loses its lease raises
    ``AnalysisLeaseLost`` instead of writing over the new owner's work.
    """
    job = claim_analysis_job(
        job_id,
        worker_id=worker_id,
        lease_seconds=lease_seconds,
    )
    if job is None:
        return None
    handler = handler or run_rule_based_analysis
    try:
        outcome = handler(job, lease_seconds=lease_seconds)
    except AnalysisLeaseLost:
        raise
    except Exception as exc:
        non_retryable = isinstance(
            exc,
            (
                AnalysisJobRejected,
                ChatAnalysisPermissionError,
                ChatAnalysisError,
            ),
        )
        failed = fail_analysis_job(
            job,
            worker_id=worker_id,
            fencing_token=job.fencing_token,
            error=f"{type(exc).__name__}: {exc}",
            retryable=not non_retryable,
            max_attempts=max_attempts,
        )
        return ExecutionResult(job=failed, handler_result={"error": str(exc)})
    if not isinstance(outcome, dict):
        outcome = {}
    completed = complete_analysis_job(
        job,
        worker_id=worker_id,
        fencing_token=job.fencing_token,
        checkpoint=outcome.get("checkpoint"),
        result_ref=outcome.get("result_ref"),
        partial=bool(outcome.get("partial")),
    )
    return ExecutionResult(job=completed, handler_result=outcome)


def _ensure_job_runnable(job):
    if job.space.status != Space.Status.ACTIVE:
        raise AnalysisJobRejected("Space is not active.")
    if not SpacePermissionService.can_upload(job.created_by, job.space):
        raise AnalysisJobRejected(
            "The initiating user can no longer write to the space."
        )


def _message_texts(message):
    return [
        part.text.strip()
        for part in message.parts.all()
        if part.kind == MessagePart.Kind.TEXT
        and part.text
        and part.text.strip()
    ]


def _write_chunk_note(job, messages):
    """Create or refresh the automatic Note for one message chunk."""
    conversation = job.conversation
    lines = []
    occurred_at = []
    missing_content = False
    for message in messages:
        if message.occurred_at:
            occurred_at.append(message.occurred_at)
        texts = _message_texts(message)
        if not texts:
            missing_content = True
            continue
        if message.occurred_at:
            stamp = timezone.localtime(message.occurred_at).strftime(
                "%Y-%m-%d %H:%M"
            )
        else:
            stamp = "unknown-time"
        sender = message.sender_name or message.sender_key or "unknown"
        lines.append(f"[{stamp}] {sender}: {' / '.join(texts)}")
    if not lines:
        return False, True
    first_seq = messages[0].ingest_seq
    last_seq = messages[-1].ingest_seq
    title = (
        f"{conversation.title or conversation.identity_key} "
        f"#{first_seq}-{last_seq}"
    )[:500]
    note = create_note(
        actor=job.created_by,
        space=job.space,
        note_key=f"job:{job.uuid}:{first_seq}-{last_seq}",
        title=title,
        content="\n".join(lines),
        start_at=min(occurred_at) if occurred_at else None,
        end_at=max(occurred_at) if occurred_at else None,
        analysis_job=job,
    )
    if note.origin == Note.Origin.MANUAL:
        return False, missing_content
    for message in messages:
        add_note_evidence(
            actor=job.created_by,
            note=note,
            message=message,
        )
    return True, missing_content


def run_rule_based_analysis(job, *, lease_seconds=DEFAULT_LEASE_SECONDS):
    """Deterministic extractor: chunked Notes plus message evidence.

    It resumes after ``checkpoint["last_ingest_seq"]`` and renews the lease
    after each chunk, so a crashed attempt can be retried without duplicating
    Notes or evidence.
    """
    _ensure_job_runnable(job)
    checkpoint = dict(job.checkpoint or {})
    last_seq = int(checkpoint.get("last_ingest_seq", job.start_seq))
    messages_processed = int(checkpoint.get("messages_processed", 0))
    notes_written = int(checkpoint.get("notes_written", 0))
    partial = bool(checkpoint.get("partial", False))

    while True:
        messages = list(
            Message.objects.filter(
                conversation_id=job.conversation_id,
                ingest_seq__gt=last_seq,
                ingest_seq__lte=job.end_seq,
            )
            .prefetch_related("parts")
            .order_by("ingest_seq")[:ANALYSIS_CHUNK_SIZE]
        )
        if not messages:
            break
        written, chunk_partial = _write_chunk_note(job, messages)
        partial = partial or chunk_partial
        notes_written += int(written)
        messages_processed += len(messages)
        last_seq = messages[-1].ingest_seq
        checkpoint = {
            "last_ingest_seq": last_seq,
            "messages_processed": messages_processed,
            "notes_written": notes_written,
            "partial": partial,
        }
        job = renew_analysis_lease(
            job,
            worker_id=job.lease_owner,
            fencing_token=job.fencing_token,
            lease_seconds=lease_seconds,
            checkpoint=checkpoint,
        )

    return {
        "checkpoint": checkpoint,
        "partial": partial,
        "result_ref": {
            "messages_processed": messages_processed,
            "notes_written": notes_written,
            "last_ingest_seq": last_seq,
        },
    }

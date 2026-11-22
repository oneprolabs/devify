"""Build bounded scheduled jobs from fully ingested messages."""

import uuid

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Exists, F, OuterRef
from django.utils import timezone

from chat_analysis.models import (
    AnalysisJob,
    AnalysisJobMessage,
    NoteEvidence,
    ScheduledAnalysisRun,
)
from chat_analysis.schedule_window import (
    DEFAULT_SCHEDULE,
    due_slot,
    slot_boundary,
)
from chat_analysis.services import create_analysis_job
from chat_domain.models import Conversation, Message, MessageOrigin
from chat_ingestion.models import UploadBatch

MAX_MESSAGES_PER_JOB = 1000
LEGACY_OVERSIZE_ERROR = "Message exceeds the model input budget."


def ensure_due_run(now, schedule=None):
    if schedule is None:
        schedule = getattr(
            settings, "CHAT_ANALYSIS_SCHEDULE", DEFAULT_SCHEDULE
        )
    slot = due_slot(now, schedule)
    if slot is None:
        return None
    return ScheduledAnalysisRun.objects.get_or_create(
        slot=slot, defaults={"boundary": slot_boundary(slot)}
    )[0]


def dispatch_due_analysis(now=None, schedule=None):
    """Open the latest started Beijing slot and schedule ready conversations.

    The cutoff is the slot clock time, not the moment the beat wakes up.
    A late wake still uses the latest hourly cutoff. Later uploads wait for
    the next slot; continuations keep their original cutoff.
    """
    now = now or timezone.now()
    run = ensure_due_run(now, schedule)
    if run is None:
        return {"jobs": 0}
    jobs = 0
    pending = _pending_origins(run.boundary)
    busy = AnalysisJob.objects.filter(
        state__in=(AnalysisJob.State.QUEUED, AnalysisJob.State.RUNNING),
    ).values("created_by_id")
    limit = max(1, settings.CHAT_ANALYSIS_DISPATCH_LIMIT)
    users = list(
        pending.exclude(upload_item__batch__uploaded_by_id__in=busy)
        .order_by("upload_item__batch__uploaded_by_id")
        .values_list("upload_item__batch__uploaded_by_id", flat=True)
        .distinct()[:limit]
    )
    partial_users = (
        AnalysisJob.objects.filter(
            state=AnalysisJob.State.PARTIAL,
            scheduled_messages__isnull=False,
            scheduled_messages__completed_at__isnull=True,
        )
        .exclude(created_by_id__in=busy)
        .exclude(
            created_by_id__in=users,
        )
        .order_by("created_by_id")
        .values_list(
            "created_by_id",
            flat=True,
        )
        .distinct()[: max(0, limit - len(users))]
    )
    for user_id in users + list(partial_users):
        jobs += int(schedule_user(user_id, run.boundary) is not None)
    return {"jobs": jobs, "slot": run.slot}


def _pending_origins(boundary, user_id=None):
    analyzed = NoteEvidence.objects.filter(
        message_id=OuterRef("message_id"),
        note__analysis_job__state=AnalysisJob.State.READY,
        note__analysis_job__conversation_id=OuterRef(
            "message__conversation_id"
        ),
    )
    origins = (
        MessageOrigin.objects.filter(
            created_at__lte=boundary,
            upload_item__batch__status=UploadBatch.Status.COMPLETED,
            upload_item__batch__completed_at__lte=boundary,
            message__created_at__lte=boundary,
            message__orphaned_at__isnull=True,
            message__scheduled_analysis__isnull=True,
            upload_item__batch__space_id=F("message__conversation__space_id"),
        )
        .annotate(analyzed=Exists(analyzed))
        .filter(analyzed=False)
    )
    if user_id is not None:
        origins = origins.filter(upload_item__batch__uploaded_by_id=user_id)
    return origins


def schedule_user(user_id, boundary, *, dispatch=True):
    """Keep the round in existing message assignments and conversation jobs."""
    with transaction.atomic():
        get_user_model().objects.select_for_update().get(pk=user_id)
        if AnalysisJob.objects.filter(
            created_by_id=user_id,
            state__in=(AnalysisJob.State.QUEUED, AnalysisJob.State.RUNNING),
        ).exists():
            return None
        partial = (
            AnalysisJob.objects.filter(
                created_by_id=user_id,
                state=AnalysisJob.State.PARTIAL,
                scheduled_messages__completed_at__isnull=True,
                scheduled_messages__error__in=("", LEGACY_OVERSIZE_ERROR),
            )
            .order_by("updated_at")
            .first()
        )
        conversation_id = (
            partial.conversation_id
            if partial
            else _pending_origins(boundary, user_id)
            .order_by("message__conversation_id")
            .values_list("message__conversation_id", flat=True)
            .first()
        )
        if conversation_id is None:
            return None
        return schedule_conversation(
            conversation_id,
            boundary,
            user_id=user_id,
            dispatch=dispatch,
        )


def schedule_conversation(
    conversation_id,
    boundary,
    *,
    user_id=None,
    dispatch=True,
):
    """Reserve a finite window at the caller's cutoff."""
    from chat_analysis.tasks import dispatch_analysis_job

    with transaction.atomic():
        conversation = (
            Conversation.objects.select_for_update()
            .select_related("space")
            .get(pk=conversation_id)
        )
        if AnalysisJob.objects.filter(
            conversation=conversation,
            state__in=(AnalysisJob.State.QUEUED, AnalysisJob.State.RUNNING),
        ).exists():
            return None
        partials = AnalysisJob.objects.filter(
            conversation=conversation,
            state=AnalysisJob.State.PARTIAL,
        )
        if user_id is not None:
            partials = partials.filter(created_by_id=user_id)
        retryable = []
        for partial in partials:
            unfinished = partial.scheduled_messages.filter(
                completed_at__isnull=True
            )
            skipped = unfinished.filter(error=LEGACY_OVERSIZE_ERROR)
            first_skipped_seq = (
                skipped.order_by("message__ingest_seq")
                .values_list("message__ingest_seq", flat=True)
                .first()
            )
            if first_skipped_seq is not None:
                # Completed assignments stay excluded when the cursor rewinds.
                checkpoint = dict(partial.checkpoint or {})
                checkpoint["last_ingest_seq"] = min(
                    checkpoint.get("last_ingest_seq", partial.start_seq),
                    first_skipped_seq - 1,
                )
                checkpoint["partial"] = False
                partial.checkpoint = checkpoint
                partial.attempts = 0
                partial.save(
                    update_fields=("checkpoint", "attempts", "updated_at")
                )
                skipped.update(error="")
            if unfinished.filter(error="").exists():
                retryable.append(partial)
        if retryable:
            for partial in retryable[:1]:
                partial.state = AnalysisJob.State.QUEUED
                partial.lease_owner = ""
                partial.lease_until = None
                partial.error = ""
                partial.save(
                    update_fields=(
                        "state",
                        "lease_owner",
                        "lease_until",
                        "error",
                        "updated_at",
                    )
                )
                resumed = partial
                if dispatch:
                    transaction.on_commit(
                        lambda job=resumed: dispatch_analysis_job(job)
                    )
            return retryable[0]
        eligible_origins = MessageOrigin.objects.filter(
            message_id=OuterRef("pk"),
            created_at__lte=boundary,
            upload_item__batch__space_id=conversation.space_id,
            upload_item__batch__status=UploadBatch.Status.COMPLETED,
            upload_item__batch__completed_at__lte=boundary,
        )
        if user_id is not None:
            eligible_origins = eligible_origins.filter(
                upload_item__batch__uploaded_by_id=user_id,
            )
        analyzed_evidence = NoteEvidence.objects.filter(
            message_id=OuterRef("pk"),
            note__space_id=conversation.space_id,
            note__analysis_job__conversation_id=conversation.pk,
            note__analysis_job__state=AnalysisJob.State.READY,
        )
        messages = list(
            Message.objects.filter(
                conversation=conversation,
                orphaned_at__isnull=True,
                scheduled_analysis__isnull=True,
                created_at__lte=boundary,
            )
            .annotate(
                eligible=Exists(eligible_origins),
                already_analyzed=Exists(analyzed_evidence),
            )
            .filter(eligible=True, already_analyzed=False)
            .order_by("ingest_seq", "pk")[
                : min(
                    MAX_MESSAGES_PER_JOB,
                    max(
                        1,
                        settings.CHAT_ANALYSIS_BATCH_MESSAGES,
                    ),
                )
            ]
        )
        if not messages:
            return None
        batches = UploadBatch.objects.filter(
            space=conversation.space,
            status=UploadBatch.Status.COMPLETED,
            completed_at__lte=boundary,
            items__chat_message_origins__message=messages[0],
            items__chat_message_origins__created_at__lte=boundary,
        )
        if user_id is not None:
            batches = batches.filter(uploaded_by_id=user_id)
        batch = (
            batches.select_related("uploaded_by")
            .order_by("completed_at", "pk")
            .first()
        )
        if batch is None:
            return None
        if (
            user_id is not None
            and AnalysisJob.objects.filter(
                created_by=batch.uploaded_by,
                state__in=(
                    AnalysisJob.State.QUEUED,
                    AnalysisJob.State.RUNNING,
                ),
            ).exists()
        ):
            return None
        job = create_analysis_job(
            actor=batch.uploaded_by,
            space=conversation.space,
            conversation=conversation,
            request_key=f"scheduled:{uuid.uuid4()}",
            start_seq=messages[0].ingest_seq - 1,
            end_seq=messages[-1].ingest_seq,
            input_version="scheduled.v1",
            specification={
                "scheduled_message_scope": True,
                "boundary": boundary.isoformat(),
            },
        )
        AnalysisJobMessage.objects.bulk_create(
            [
                AnalysisJobMessage(job=job, message=message)
                for message in messages
            ]
        )
        job.upload_batches.set(
            UploadBatch.objects.filter(
                space=conversation.space,
                status=UploadBatch.Status.COMPLETED,
                completed_at__lte=boundary,
                items__chat_message_origins__message__in=messages,
                items__chat_message_origins__created_at__lte=boundary,
            ).distinct()
        )
        if dispatch:
            transaction.on_commit(lambda: dispatch_analysis_job(job))
        return job

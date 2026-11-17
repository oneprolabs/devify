"""Build bounded scheduled jobs from fully ingested messages."""

import uuid

from django.db import transaction
from django.conf import settings
from django.db.models import Exists, OuterRef
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
        schedule = getattr(settings, "CHAT_ANALYSIS_SCHEDULE", DEFAULT_SCHEDULE)
    slot = due_slot(now, schedule)
    if slot is None:
        return None
    return ScheduledAnalysisRun.objects.get_or_create(
        slot=slot, defaults={"boundary": slot_boundary(slot)}
    )[0]


def dispatch_due_analysis(now=None, schedule=None):
    """Open the latest started Beijing slot and schedule ready conversations.

    The cutoff is the slot clock time, not the moment the beat wakes up.
    A late wake still uses 11:00 or 18:00, so messages stored afterwards
    stay for the next slot.
    """
    now = now or timezone.now()
    run = ensure_due_run(now, schedule)
    if run is None:
        return {"jobs": 0}
    conversation_ids = set(
        Conversation.objects.filter(
            messages__scheduled_analysis__isnull=True,
            messages__orphaned_at__isnull=True,
            messages__created_at__lte=run.boundary,
        ).values_list("pk", flat=True)
    )
    conversation_ids.update(
        AnalysisJob.objects.filter(
            state=AnalysisJob.State.PARTIAL
        ).values_list("conversation_id", flat=True)
    )
    jobs = 0
    for conversation_id in conversation_ids:
        if schedule_conversation(conversation_id, run.boundary) is not None:
            jobs += 1
    return {"jobs": jobs, "slot": run.slot}


def schedule_conversation(conversation_id, boundary):
    """Reserve one finite window; the caller controls the schedule and boundary."""
    with transaction.atomic():
        conversation = Conversation.objects.select_for_update().select_related("space").get(pk=conversation_id)
        if AnalysisJob.objects.filter(
            conversation=conversation,
            state__in=(AnalysisJob.State.QUEUED, AnalysisJob.State.RUNNING),
        ).exists():
            return None
        partials = list(
            AnalysisJob.objects.filter(
                conversation=conversation, state=AnalysisJob.State.PARTIAL
            )
        )
        retryable = []
        for partial in partials:
            unfinished = partial.scheduled_messages.filter(completed_at__isnull=True)
            skipped = unfinished.filter(error=LEGACY_OVERSIZE_ERROR)
            first_skipped_seq = skipped.order_by("message__ingest_seq").values_list(
                "message__ingest_seq", flat=True
            ).first()
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
                partial.save(update_fields=("checkpoint", "attempts", "updated_at"))
                skipped.update(error="")
            if unfinished.filter(error="").exists():
                retryable.append(partial)
        if retryable:
            from chat_analysis.tasks import dispatch_analysis_job

            for partial in retryable:
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
                transaction.on_commit(
                    lambda job=resumed: dispatch_analysis_job(job)
                )
            return retryable[0]
        eligible_origins = MessageOrigin.objects.filter(
            message_id=OuterRef("pk"), created_at__lte=boundary,
            upload_item__batch__space_id=conversation.space_id,
            upload_item__batch__status=UploadBatch.Status.COMPLETED,
            upload_item__batch__completed_at__lte=boundary,
        )
        analyzed_evidence = NoteEvidence.objects.filter(
            message_id=OuterRef("pk"), note__space_id=conversation.space_id,
            note__analysis_job__conversation_id=conversation.pk,
            note__analysis_job__state=AnalysisJob.State.READY,
        )
        messages = list(Message.objects.filter(
            conversation=conversation, orphaned_at__isnull=True,
            scheduled_analysis__isnull=True, created_at__lte=boundary,
        ).annotate(eligible=Exists(eligible_origins), already_analyzed=Exists(analyzed_evidence)).filter(eligible=True, already_analyzed=False).order_by("ingest_seq", "pk")[:MAX_MESSAGES_PER_JOB])
        if not messages:
            return None
        batch = UploadBatch.objects.filter(
            space=conversation.space, status=UploadBatch.Status.COMPLETED,
            completed_at__lte=boundary, items__chat_message_origins__message=messages[0],
            items__chat_message_origins__created_at__lte=boundary,
        ).select_related("uploaded_by").order_by("completed_at", "pk").first()
        if batch is None:
            return None
        from chat_analysis.tasks import dispatch_analysis_job

        job = create_analysis_job(
            actor=batch.uploaded_by, space=conversation.space, conversation=conversation,
            request_key=f"scheduled:{uuid.uuid4()}", start_seq=messages[0].ingest_seq - 1,
            end_seq=messages[-1].ingest_seq, input_version="scheduled.v1",
            specification={"scheduled_message_scope": True, "boundary": boundary.isoformat()},
        )
        AnalysisJobMessage.objects.bulk_create([AnalysisJobMessage(job=job, message=message) for message in messages])
        job.upload_batches.set(UploadBatch.objects.filter(
            space=conversation.space, status=UploadBatch.Status.COMPLETED,
            completed_at__lte=boundary, items__chat_message_origins__message__in=messages,
            items__chat_message_origins__created_at__lte=boundary,
        ).distinct())
        transaction.on_commit(lambda: dispatch_analysis_job(job))
        return job

"""Celery tasks for chat upload processing."""

from celery import shared_task
from django.shortcuts import get_object_or_404

from chat_ingestion.models import UploadBatch
from chat_ingestion.parsing import parse_archive
from chat_ingestion.services import UploadTransitionError, transition_batch
from spaces.services import SpacePermissionService, audit_space_action


@shared_task(bind=True, max_retries=3)
def parse_chat_upload_task(self, batch_id):
    """Parse one processing batch outside the API request."""
    batch = get_object_or_404(
        UploadBatch.objects.select_related("space", "uploaded_by"),
        pk=batch_id,
    )
    if batch.status == UploadBatch.Status.COMPLETED:
        return {"batch_id": batch.pk, "status": batch.status}
    if batch.status != UploadBatch.Status.PROCESSING:
        return {"batch_id": batch.pk, "status": batch.status}
    if (
        batch.space.status != batch.space.Status.ACTIVE
        or not SpacePermissionService.can_upload(
            batch.uploaded_by, batch.space
        )
    ):
        batch.status = UploadBatch.Status.FAILED
        batch.error_message = (
            "The upload is no longer authorized for this space."
        )
        batch.save(update_fields=("status", "error_message", "updated_at"))
        return {"batch_id": batch.pk, "status": batch.status}
    try:
        batch = parse_archive(batch, retry_transient=True)
    except UploadTransitionError:
        batch.refresh_from_db()
        return {"batch_id": batch.pk, "status": batch.status}
    except (RuntimeError, OSError) as error:
        if getattr(self.request, "retries", 0) >= self.max_retries:
            batch.refresh_from_db()
            if batch.status == UploadBatch.Status.PROCESSING:
                transition_batch(
                    batch,
                    UploadBatch.Status.FAILED,
                    error_message=str(error),
                )
            return {
                "batch_id": batch.pk,
                "status": UploadBatch.Status.FAILED,
            }
        raise self.retry(exc=error, countdown=30)

    audit_space_action(
        actor=batch.uploaded_by,
        space=batch.space,
        action="chat.upload_completed",
        resource_type="upload_batch",
        resource_id=batch.pk,
        metadata={
            "archive_sha256": batch.archive_sha256,
            "status": batch.status,
            "message_count": batch.message_count,
            "duplicate_count": batch.duplicate_count,
            "error": batch.error_message or None,
        },
    )
    return {
        "batch_id": batch.pk,
        "status": batch.status,
        "message_count": batch.message_count,
        "duplicate_count": batch.duplicate_count,
    }


def dispatch_parse_chat_upload(batch):
    return parse_chat_upload_task.delay(batch.pk)

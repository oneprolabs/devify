"""Allowed upload batch state transitions."""

from django.utils import timezone

from chat_ingestion.models import UploadBatch
from chat_ingestion.services.exceptions import UploadTransitionError

ALLOWED_TRANSITIONS = {
    UploadBatch.Status.CREATED: frozenset(
        {UploadBatch.Status.UPLOADING, UploadBatch.Status.CANCELLED}
    ),
    UploadBatch.Status.UPLOADING: frozenset(
        {
            UploadBatch.Status.PROCESSING,
            UploadBatch.Status.FAILED,
            UploadBatch.Status.CANCELLED,
        }
    ),
    UploadBatch.Status.PROCESSING: frozenset(
        {UploadBatch.Status.COMPLETED, UploadBatch.Status.FAILED}
    ),
    UploadBatch.Status.FAILED: frozenset(
        {UploadBatch.Status.UPLOADING, UploadBatch.Status.CANCELLED}
    ),
    UploadBatch.Status.COMPLETED: frozenset(),
    UploadBatch.Status.CANCELLED: frozenset(),
}


def transition_batch(batch, status, *, error_message=None, save=True):
    """Move a batch to ``status``, enforcing the upload state machine."""

    if status == batch.status:
        raise UploadTransitionError(f"Upload already in status '{status}'.")
    if status not in ALLOWED_TRANSITIONS.get(batch.status, frozenset()):
        raise UploadTransitionError(
            f"Cannot move upload from '{batch.status}' to '{status}'."
        )
    batch.status = status
    if error_message is not None:
        batch.error_message = error_message
    update_fields = ["status", "error_message", "updated_at"]
    if status == UploadBatch.Status.PROCESSING:
        batch.parse_started_at = timezone.now()
        update_fields.append("parse_started_at")
    if status == UploadBatch.Status.COMPLETED:
        batch.completed_at = timezone.now()
        update_fields.append("completed_at")
    if save:
        batch.save(update_fields=update_fields)
    return batch

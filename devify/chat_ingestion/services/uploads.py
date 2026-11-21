"""Upload completion, cancellation, and contribution withdrawal."""

from django.db import transaction
from django.utils import timezone

from chat_ingestion.models import UploadBatch
from chat_ingestion.services.archives import archive_exists, archive_path
from chat_ingestion.services.exceptions import ArchiveMissing, RevokeRejected
from chat_ingestion.services.state import transition_batch
from spaces.services import SpacePermissionService


def complete_upload(batch):
    """Accept a fully uploaded archive and queue the batch for processing."""

    if not archive_exists(batch):
        raise ArchiveMissing("Archive upload is required before completion.")
    return transition_batch(batch, UploadBatch.Status.PROCESSING)


def cancel_upload(batch):
    return transition_batch(batch, UploadBatch.Status.CANCELLED)


@transaction.atomic
def revoke_upload(batch, *, actor):
    """Withdraw one uploader's contribution without touching anyone else's.

    Only the batch's own origins, items and archive are removed. A message
    that another upload also carries keeps its other origins and stays
    visible; a message left without any origin is marked orphaned so it stops
    feeding new analysis while remaining readable for audit.

    Returns counts for the audit entry.
    """

    # Imported here: chat_domain depends on chat_ingestion models, not the
    # other way around, and this keeps the import graph acyclic at startup.
    from chat_domain.models import Message, MessageOrigin

    batch = (
        UploadBatch.objects.select_for_update()
        .select_related("space")
        .get(pk=batch.pk)
    )
    if batch.status == UploadBatch.Status.PROCESSING:
        raise RevokeRejected(
            "An upload that is still processing cannot be revoked."
        )
    if not SpacePermissionService.can_delete_resource(
        actor, batch.space, batch.uploaded_by_id
    ):
        raise PermissionError(
            "Only the uploader or a space administrator can revoke an upload."
        )

    message_ids = list(
        MessageOrigin.objects.filter(upload_item__batch=batch)
        .values_list("message_id", flat=True)
        .distinct()
    )
    origin_count = MessageOrigin.objects.filter(
        upload_item__batch=batch
    ).count()
    MessageOrigin.objects.filter(upload_item__batch=batch).delete()

    orphaned = 0
    if message_ids:
        now = timezone.now()
        for message in Message.objects.filter(pk__in=message_ids):
            if message.origins.exists():
                continue
            message.orphaned_at = now
            message.save(update_fields=("orphaned_at", "updated_at"))
            orphaned += 1

    archive = archive_path(batch)
    if archive.is_file():
        archive.unlink()
    item_count = batch.items.count()
    batch.delete()
    return {
        "messages": len(message_ids),
        "orphaned": orphaned,
        "items": item_count,
        "origins": origin_count,
    }

"""Celery tasks for chat upload processing."""

import logging

from celery import shared_task
from django.conf import settings
from django.db import models
from django.shortcuts import get_object_or_404
from django.utils import timezone

from chat_analysis.services import create_analysis_job
from chat_analysis.execution import execute_analysis_job
from chat_analysis.tasks import dispatch_analysis_job
from chat_domain.models import Conversation, Message
from chat_ingestion.models import UploadBatch
from chat_ingestion.parsing import parse_archive
from chat_ingestion.services import UploadTransitionError, transition_batch
from chat_sources.models import SourceImport
from spaces.services import SpacePermissionService, audit_space_action

logger = logging.getLogger(__name__)


def _enqueue_analysis_for_batch(batch):
    if batch.message_count <= 0:
        return 0
    jobs = 0
    conversations = Conversation.objects.filter(
        space=batch.space,
        messages__origins__upload_item__batch=batch,
    ).distinct()
    for conversation in conversations:
        bounds = Message.objects.filter(
            conversation=conversation,
            origins__upload_item__batch=batch,
        ).aggregate(
            min_seq=models.Min("ingest_seq"), max_seq=models.Max("ingest_seq")
        )
        if bounds["min_seq"] is None or bounds["max_seq"] is None:
            continue
        try:
            job = create_analysis_job(
                actor=batch.uploaded_by,
                space=batch.space,
                conversation=conversation,
                request_key=f"upload:{batch.uuid}:{conversation.pk}",
                start_seq=bounds["min_seq"] - 1,
                end_seq=bounds["max_seq"],
                input_version=f"{batch.source_type}.v1",
            )
            if getattr(settings, "CHAT_UPLOAD_ANALYSIS_INLINE", False):
                execute_analysis_job(
                    job.pk,
                    worker_id=f"inline:upload:{batch.pk}",
                )
            else:
                dispatch_analysis_job(job)
            jobs += 1
        except Exception as error:
            logger.warning(
                "Failed to enqueue analysis for upload %s conversation %s: %s",
                batch.pk,
                conversation.pk,
                error,
            )
    return jobs


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
    source_import = SourceImport.objects.filter(upload_batch=batch).first()
    if source_import:
        source_import.status = SourceImport.Status.RUNNING
        source_import.started_at = source_import.started_at or timezone.now()
        source_import.save(
            update_fields=("status", "started_at", "updated_at")
        )
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
        if source_import:
            source_import.status = SourceImport.Status.FAILED
            source_import.error_message = batch.error_message
            source_import.completed_at = timezone.now()
            source_import.save(
                update_fields=(
                    "status",
                    "error_message",
                    "completed_at",
                    "updated_at",
                )
            )
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
    if source_import:
        source_import.status = {
            UploadBatch.Status.COMPLETED: SourceImport.Status.COMPLETED,
            UploadBatch.Status.FAILED: SourceImport.Status.FAILED,
        }.get(batch.status, SourceImport.Status.PARTIAL)
        source_import.accepted_count = batch.message_count
        source_import.duplicate_count = batch.duplicate_count
        source_import.failed_count = int(
            batch.status == UploadBatch.Status.FAILED
        )
        source_import.error_message = batch.error_message
        source_import.completed_at = timezone.now()
        source_import.save(
            update_fields=(
                "status",
                "accepted_count",
                "duplicate_count",
                "failed_count",
                "error_message",
                "completed_at",
                "updated_at",
            )
        )
    analysis_jobs = _enqueue_analysis_for_batch(batch)
    return {
        "batch_id": batch.pk,
        "status": batch.status,
        "message_count": batch.message_count,
        "duplicate_count": batch.duplicate_count,
        "analysis_jobs": analysis_jobs,
    }


def dispatch_parse_chat_upload(batch):
    return parse_chat_upload_task.delay(batch.pk)

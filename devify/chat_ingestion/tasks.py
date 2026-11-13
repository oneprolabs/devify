"""Celery tasks for chat upload processing."""

import hashlib
import json
import logging

from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded
from chat_sources.models import SourceImport
from django.conf import settings
from django.db import models
from django.shortcuts import get_object_or_404
from django.utils import timezone

from chat_analysis.execution import execute_analysis_job
from chat_analysis.models import AnalysisJob
from chat_analysis.services import (
    create_analysis_job,
    get_analysis_preferences,
    retry_analysis_job,
)
from chat_analysis.tasks import dispatch_analysis_job
from chat_domain.models import Conversation, Message
from chat_ingestion.models import UploadBatch
from chat_ingestion.parsing import parse_archive
from chat_ingestion.services import UploadTransitionError, transition_batch
from spaces.models import (
    canonicalize_chat_analysis_preferences,
    default_chat_analysis_preferences,
)
from spaces.services import SpacePermissionService, audit_space_action

logger = logging.getLogger(__name__)


def _enqueue_analysis_for_batch(batch):
    """Deduplicate by conversation content and effective analysis settings."""

    if batch.message_count <= 0 and not batch.duplicate_count:
        return {"jobs": 0, "duplicates": 0, "retried": 0}
    jobs = 0
    duplicates = 0
    retried = 0
    digests = batch.conversation_digests or {}
    preferences = get_analysis_preferences(batch.space)
    preference_digest = hashlib.sha256(
        json.dumps(preferences, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()
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
        digest = digests.get(str(conversation.pk))
        legacy_key = f"upload:{conversation.pk}:{digest}" if digest else None
        content_key = legacy_key or f"upload:{batch.uuid}:{conversation.pk}"
        request_key = (
            f"{content_key}:prefs:{preference_digest}:kind:{conversation.kind}"
        )
        try:
            existing = AnalysisJob.objects.filter(
                space=batch.space, request_key=request_key
            ).first()
            if existing is None and legacy_key:
                legacy = AnalysisJob.objects.filter(
                    space=batch.space, request_key=legacy_key
                ).first()
                if legacy is not None:
                    snapshot = (legacy.specification or {}).get(
                        "chat_analysis_preferences"
                    )
                    result = legacy.result_ref
                    skipped = (
                        isinstance(snapshot, dict)
                        and isinstance(result, dict)
                        and type(result.get("messages_processed")) is int
                        and result["messages_processed"] == 0
                    )
                    if not skipped and (
                        (
                            isinstance(snapshot, dict)
                            and canonicalize_chat_analysis_preferences(
                                snapshot
                            ) == preferences
                        )
                        or (
                            snapshot is None
                            and preferences
                            == default_chat_analysis_preferences()
                        )
                    ):
                        existing = legacy
            if existing is not None:
                existing.upload_batches.add(batch)
                duplicates += 1
                if existing.state in (
                    AnalysisJob.State.FAILED,
                    AnalysisJob.State.CANCELLED,
                ):
                    existing = retry_analysis_job(
                        actor=batch.uploaded_by, job=existing
                    )
                    if getattr(settings, "CHAT_UPLOAD_ANALYSIS_INLINE", False):
                        execute_analysis_job(
                            existing.pk,
                            worker_id=f"inline:upload:{batch.pk}",
                        )
                    else:
                        dispatch_analysis_job(existing)
                    retried += 1
                continue
            job = create_analysis_job(
                actor=batch.uploaded_by,
                space=batch.space,
                conversation=conversation,
                request_key=request_key,
                start_seq=bounds["min_seq"] - 1,
                end_seq=bounds["max_seq"],
                input_version=f"{batch.source_type}.v1",
                analysis_preferences=preferences,
            )
            job.upload_batches.add(batch)
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
    return {"jobs": jobs, "duplicates": duplicates, "retried": retried}


@shared_task(bind=True, max_retries=3)
def parse_chat_upload_task(self, batch_id):
    """Parse one processing batch outside the API request."""
    batch = get_object_or_404(
        UploadBatch.objects.select_related("space", "uploaded_by"),
        pk=batch_id,
    )
    if batch.status == UploadBatch.Status.COMPLETED:
        if not AnalysisJob.objects.filter(upload_batches=batch).exists():
            _enqueue_analysis_for_batch(batch)
        return {"batch_id": batch.pk, "status": batch.status}
    if batch.status != UploadBatch.Status.PROCESSING:
        return {"batch_id": batch.pk, "status": batch.status}
    source_import = getattr(batch, "source_import", None)
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
    except SoftTimeLimitExceeded:
        batch.refresh_from_db()
        if batch.status == UploadBatch.Status.PROCESSING:
            transition_batch(
                batch, UploadBatch.Status.FAILED,
                error_message="Upload processing exceeded the time limit.",
            )
        if source_import:
            source_import.status = SourceImport.Status.FAILED
            source_import.error_message = batch.error_message
            source_import.completed_at = timezone.now()
            source_import.save(update_fields=(
                "status", "error_message", "completed_at", "updated_at",
            ))
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
    analysis = _enqueue_analysis_for_batch(batch)
    return {
        "batch_id": batch.pk,
        "status": batch.status,
        "message_count": batch.message_count,
        "duplicate_count": batch.duplicate_count,
        "analysis_jobs": analysis["jobs"],
        "analysis_duplicates": analysis["duplicates"],
        "analysis_retried": analysis["retried"],
    }


def dispatch_parse_chat_upload(batch):
    return parse_chat_upload_task.delay(batch.pk)


@shared_task
def recover_stale_uploads_task():
    from chat_ingestion.recovery import recover_stale_uploads

    return recover_stale_uploads()

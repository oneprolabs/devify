"""Recover upload parsing tasks without interrupting active parsers."""

import hashlib
import logging
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from chat_ingestion.models import UploadBatch
from chat_ingestion.services import archive_path, transition_batch

logger = logging.getLogger(__name__)
STALE_SECONDS = 900
MAX_BATCHES = 50


def _archive_is_valid(batch):
    if not batch.archive_sha256 or batch.archive_size is None:
        return False
    try:
        path = archive_path(batch)
        if path.stat().st_size != batch.archive_size:
            return False
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest() == batch.archive_sha256.lower()
    except FileNotFoundError:
        return False
    except OSError:
        logger.exception(
            "Cannot verify chat upload archive for batch %s", batch.pk
        )
        return None


def recover_stale_uploads(*, now=None, stale_seconds=STALE_SECONDS):
    """Requeue verified batches without touching in-flight uploads."""
    from chat_ingestion.tasks import dispatch_parse_chat_upload

    cutoff = (now or timezone.now()) - timedelta(seconds=stale_seconds)
    candidates = list(
        UploadBatch.objects.filter(
            status=UploadBatch.Status.PROCESSING, updated_at__lt=cutoff
        )
        .order_by("updated_at", "pk")
        .values_list("pk", flat=True)[:MAX_BATCHES]
    )
    result = {"requeued": 0, "missing_or_invalid": 0}
    for batch_id in candidates:
        with transaction.atomic():
            # Parsing holds this row lock for its entire transaction. Never
            # interrupt a parser that is still working.
            batch = (
                UploadBatch.objects.select_for_update(skip_locked=True)
                .filter(
                    pk=batch_id,
                    status=UploadBatch.Status.PROCESSING,
                    updated_at__lt=cutoff,
                )
                .first()
            )
            if batch is None:
                continue
            valid = _archive_is_valid(batch)
            if valid is None:
                continue
            if not valid:
                transition_batch(
                    batch,
                    UploadBatch.Status.FAILED,
                    error_message="上传归档缺失或校验失败，请检查服务端共享存储后重试。",
                )
                result["missing_or_invalid"] += 1
                continue
            # Refresh the timestamp to throttle repeat sweeps.
            batch.worker_started_at = None
            batch.save(update_fields=("worker_started_at", "updated_at"))

            def dispatch(batch=batch):
                try:
                    dispatch_parse_chat_upload(batch)
                except Exception:
                    logger.exception(
                        "Could not requeue chat upload %s", batch.pk
                    )

            transaction.on_commit(dispatch)
            result["requeued"] += 1
    return result

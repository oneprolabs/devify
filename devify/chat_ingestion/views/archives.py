"""Upload archive transfer endpoints."""

import time

from django.db import transaction
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from chat_ingestion.models import UploadBatch
from chat_ingestion.services import (
    ArchiveMismatch,
    ArchiveTooLarge,
    store_archive,
)
from chat_ingestion.views.common import (
    _active_takeover,
    _batch_response,
    _can_operate_batch,
    _read_only_response,
    _visible_batch,
    logger,
)
from spaces.models import Space
from spaces.services import audit_space_action


class UploadBatchArchiveAPIView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    @transaction.atomic
    def put(self, request, batch_id):
        started = time.monotonic()
        logger.info("Chat archive request started: batch=%s", batch_id)
        batch = _visible_batch(request.user, batch_id, lock=True)
        if batch is None:
            return Response({"detail": "Upload not found."}, status=404)
        if batch.space.status != Space.Status.ACTIVE:
            return _read_only_response()
        if not _can_operate_batch(request.user, batch):
            return Response(
                {"detail": "Upload permission required."}, status=403
            )
        if batch.status not in (
            UploadBatch.Status.CREATED,
            UploadBatch.Status.UPLOADING,
            UploadBatch.Status.FAILED,
        ):
            return Response(
                {"detail": "Upload can no longer be modified."}, status=409
            )
        uploaded = request.FILES.get("archive")
        if uploaded is None:
            return Response(
                {"detail": "Archive file is required."}, status=400
            )
        try:
            store_archive(batch, uploaded)
        except ArchiveTooLarge as error:
            logger.warning("Chat archive too large: batch=%s", batch_id)
            return Response({"detail": str(error)}, status=413)
        except ArchiveMismatch as error:
            logger.warning(
                "Chat archive validation failed: batch=%s", batch_id
            )
            return Response({"detail": str(error)}, status=409)
        logger.info(
            "Chat archive stored: batch=%s bytes=%s elapsed_seconds=%.3f",
            batch_id,
            batch.archive_size,
            time.monotonic() - started,
        )
        takeover = _active_takeover(request.user, batch.space)
        audit_space_action(
            actor=request.user,
            space=batch.space,
            action="chat.archive_uploaded",
            resource_type="upload_batch",
            resource_id=batch.pk,
            metadata={
                "archive_sha256": batch.archive_sha256,
                "archive_size": batch.archive_size,
                "takeover_id": takeover.pk if takeover else None,
            },
        )
        return _batch_response(batch)

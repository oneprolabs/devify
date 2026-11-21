"""Upload completion, retry, and cancellation endpoints."""

from django.db import transaction
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from chat_ingestion.models import UploadBatch
from chat_ingestion.serializers import UploadBatchSerializer
from chat_ingestion.services import (
    ArchiveMissing,
    UploadTransitionError,
    cancel_upload,
    complete_upload,
    transition_batch,
)
from chat_ingestion.services.dispatch import _enqueue_parse
from chat_ingestion.views.common import (
    _active_takeover,
    _batch_response,
    _can_operate_batch,
    _read_only_response,
    _visible_batch,
)
from spaces.models import Space
from spaces.services import audit_space_action


class UploadBatchCompleteAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, batch_id):
        batch = _visible_batch(request.user, batch_id, lock=True)
        if batch is None:
            return Response({"detail": "Upload not found."}, status=404)
        if batch.space.status != Space.Status.ACTIVE:
            return _read_only_response()
        if not _can_operate_batch(request.user, batch):
            return Response(
                {"detail": "Upload permission required."}, status=403
            )
        if batch.status == UploadBatch.Status.COMPLETED:
            return _batch_response(batch)
        if batch.status != UploadBatch.Status.PROCESSING:
            try:
                complete_upload(batch)
            except (ArchiveMissing, UploadTransitionError) as error:
                return Response({"detail": str(error)}, status=409)
        result = _enqueue_parse(batch)
        if result and result.get("status") == UploadBatch.Status.FAILED:
            batch.refresh_from_db()
            return Response(
                {
                    "detail": batch.error_message,
                    "data": UploadBatchSerializer(batch).data,
                },
                status=422,
            )
        if result and result.get("status") == UploadBatch.Status.COMPLETED:
            batch.refresh_from_db()
            return _batch_response(batch)
        return _batch_response(batch, status_code=202)


class UploadBatchRetryAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, batch_id):
        batch = _visible_batch(request.user, batch_id, lock=True)
        if batch is None:
            return Response({"detail": "Upload not found."}, status=404)
        if batch.space.status != Space.Status.ACTIVE:
            return _read_only_response()
        if not _can_operate_batch(request.user, batch):
            return Response(
                {"detail": "Upload permission required."}, status=403
            )
        if batch.status != UploadBatch.Status.FAILED:
            return Response(
                {"detail": "Only failed uploads can be retried."}, status=409
            )
        try:
            transition_batch(
                batch,
                UploadBatch.Status.UPLOADING,
                error_message="",
                save=False,
            )
            complete_upload(batch)
        except (ArchiveMissing, UploadTransitionError) as error:
            return Response({"detail": str(error)}, status=409)
        result = _enqueue_parse(batch)
        if result and result.get("status") == UploadBatch.Status.FAILED:
            batch.refresh_from_db()
            return Response(
                {
                    "detail": batch.error_message,
                    "data": UploadBatchSerializer(batch).data,
                },
                status=422,
            )
        takeover = _active_takeover(request.user, batch.space)
        audit_space_action(
            actor=request.user,
            space=batch.space,
            action="chat.upload_retried",
            resource_type="upload_batch",
            resource_id=batch.pk,
            metadata={"takeover_id": takeover.pk if takeover else None},
        )
        return _batch_response(batch, status_code=202)


class UploadBatchCancelAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, batch_id):
        batch = _visible_batch(request.user, batch_id, lock=True)
        if batch is None:
            return Response({"detail": "Upload not found."}, status=404)
        if batch.space.status != Space.Status.ACTIVE:
            return _read_only_response()
        if not _can_operate_batch(request.user, batch):
            return Response(
                {"detail": "Upload permission required."}, status=403
            )
        if batch.status == UploadBatch.Status.CANCELLED:
            return _batch_response(batch)
        try:
            cancel_upload(batch)
        except UploadTransitionError as error:
            return Response({"detail": str(error)}, status=409)
        takeover = _active_takeover(request.user, batch.space)
        audit_space_action(
            actor=request.user,
            space=batch.space,
            action="chat.upload_cancelled",
            resource_type="upload_batch",
            resource_id=batch.pk,
            metadata={"takeover_id": takeover.pk if takeover else None},
        )
        return _batch_response(batch)

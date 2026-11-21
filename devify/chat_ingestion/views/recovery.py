"""Precise recovery of uncertain upload creation requests."""

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import DesktopDevice
from chat_ingestion.models import UploadBatch
from chat_ingestion.serializers import UploadBatchSerializer
from chat_ingestion.views.common import _authorized_space


class UploadBatchRecoveryAPIView(APIView):
    """Precise recovery of an uncertain create; never scan upload history."""

    permission_classes = [IsAuthenticated]

    def get(self, request, space_id):
        space = _authorized_space(request.user, space_id)
        if space is None:
            return Response({"detail": "Space not found."}, status=404)
        device_id = request.query_params.get("device_id", "")
        account = request.query_params.get("source_account_id", "")
        key = request.query_params.get("idempotency_key", "")
        digest = request.query_params.get("archive_sha256", "")
        if not device_id or not account or bool(key) == bool(digest):
            return Response(
                {
                    "detail": (
                        "Provide a device, source account "
                        "and one recovery key."
                    )
                },
                status=400,
            )
        if not DesktopDevice.objects.filter(
            user=request.user,
            device_id=device_id,
            status=DesktopDevice.Status.ACTIVE,
        ).exists():
            return Response(
                {"detail": "Device authorization is required."}, status=403
            )
        batches = UploadBatch.objects.filter(
            space=space,
            uploaded_by=request.user,
            device_id=device_id,
            source_account_id=account,
        )
        batches = (
            batches.filter(idempotency_key=key)
            if key
            else batches.filter(archive_sha256=digest)
        )
        rows = list(batches.select_related("source").order_by("-id")[:2])
        if len(rows) > 1:
            return Response(
                {"detail": "Recovery is ambiguous; retain the original task."},
                status=409,
            )
        batch = rows[0] if rows else None
        return Response(
            {
                "data": {
                    "batch": (
                        UploadBatchSerializer(batch).data if batch else None
                    ),
                    "archive_received": bool(
                        batch and batch.archive_received_at
                    ),
                }
            }
        )

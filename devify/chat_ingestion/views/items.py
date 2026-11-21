"""Upload item detail endpoints."""

from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from chat_ingestion.models import UploadItem
from chat_ingestion.serializers import UploadItemSerializer
from chat_ingestion.views.common import _visible_batch


class UploadBatchItemDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, batch_id, item_id):
        batch = _visible_batch(request.user, batch_id)
        if batch is None:
            return Response({"detail": "Upload not found."}, status=404)
        item = get_object_or_404(UploadItem, batch=batch, pk=item_id)
        return Response({"data": UploadItemSerializer(item).data})

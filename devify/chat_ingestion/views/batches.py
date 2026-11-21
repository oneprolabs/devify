"""Upload batch creation, listing, and detail endpoints."""

from chat_sources.services import get_or_create_upload_source
from django.db import transaction
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from chat_ingestion.models import UploadBatch
from chat_ingestion.serializers import (
    UploadBatchCreateSerializer,
    UploadBatchSerializer,
)
from chat_ingestion.services import RevokeRejected, revoke_upload
from chat_ingestion.services.devices import _resolve_upload_device
from chat_ingestion.services.idempotency import _idempotency_conflicts
from chat_ingestion.services.queries import (
    _analysis_summaries,
    _conversation_counts,
    _image_counts,
)
from chat_ingestion.views.common import (
    _active_takeover,
    _authorized_space,
    _authorized_space_for_read,
    _batch_response,
    _read_only_response,
    _visible_batch,
)
from spaces.models import Space, SpaceQuota
from spaces.services import (
    audit_space_action,
    check_storage_quota,
    get_space_quota,
)


class UploadBatchCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, space_id):
        space, takeover = _authorized_space_for_read(request.user, space_id)
        if space is None:
            return Response({"detail": "Space not found."}, status=404)
        batches = (
            UploadBatch.objects.filter(space=space)
            .select_related("source")
            .prefetch_related("items")
            .order_by("-created_at", "-id")
        )
        status_filter = request.query_params.get("status")
        if status_filter:
            batches = batches.filter(status=status_filter)
        paginator = PageNumberPagination()
        paginator.page_size = 25
        paginator.page_size_query_param = "page_size"
        paginator.max_page_size = 100
        page = paginator.paginate_queryset(batches, request, view=self)
        conversation_counts = _conversation_counts(page)
        image_counts = _image_counts(page)
        analysis_summaries = _analysis_summaries(page)
        for batch in page:
            batch.conversation_count = conversation_counts.get(batch.pk, 0)
            batch.image_count = image_counts.get(batch.pk, 0)
            batch.analysis_summary = analysis_summaries.get(batch.pk)
        data = UploadBatchSerializer(page, many=True).data
        if takeover:
            audit_space_action(
                actor=request.user,
                space=space,
                action="chat.upload_list_viewed",
                resource_type="upload_batch",
                metadata={"takeover_id": takeover.pk},
            )
        return Response(
            {
                "data": {
                    "list": data,
                    "pagination": {
                        "total": paginator.page.paginator.count,
                        "page": paginator.page.number,
                        "page_size": paginator.get_page_size(request),
                        "next": paginator.get_next_link(),
                        "previous": paginator.get_previous_link(),
                    },
                }
            }
        )

    @transaction.atomic
    def post(self, request, space_id):
        space = _authorized_space(request.user, space_id)
        if space is None:
            return Response({"detail": "Space not found."}, status=404)
        # Serialize quota checks and idempotency without locking the space row:
        # long imports hold a foreign-key lock on that row until they commit.
        quota = get_space_quota(space)
        SpaceQuota.objects.select_for_update().get(pk=quota.pk)
        serializer = UploadBatchCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        device_id, platform = _resolve_upload_device(request, values)
        if device_id is None:
            return Response(
                {"detail": "This device authorization was revoked."},
                status=403,
            )
        lookup = {
            "space": space,
            "uploaded_by": request.user,
            "idempotency_key": values["idempotency_key"],
        }
        batch = UploadBatch.objects.filter(**lookup).first()
        if batch is not None:
            if _idempotency_conflicts(batch, values):
                return Response(
                    {
                        "detail": (
                            "Idempotency key conflicts with existing upload."
                        )
                    },
                    status=409,
                )
            updated_fields = []
            if device_id and not batch.device_id:
                batch.device_id = device_id
                updated_fields.append("device_id")
            if platform and batch.platform != platform:
                batch.platform = platform
                updated_fields.append("platform")
            if updated_fields:
                batch.save(update_fields=(*updated_fields, "updated_at"))
            return _batch_response(batch)
        quota_error = check_storage_quota(space, values.get("archive_size"))
        if quota_error:
            return Response({"detail": quota_error}, status=413)
        source = get_or_create_upload_source(
            space=space,
            actor=request.user,
            channel_type=values["source_type"],
            account_key=values.get("source_account_id", ""),
        )
        batch = UploadBatch.objects.create(
            **lookup,
            source=source,
            source_type=values["source_type"],
            source_account_id=values.get("source_account_id") or "",
            device_id=device_id,
            platform=platform,
            trigger=values.get("trigger") or UploadBatch.Trigger.MANUAL,
            archive_sha256=(values.get("archive_sha256") or "").lower(),
            archive_size=values.get("archive_size"),
            status=UploadBatch.Status.UPLOADING,
        )
        audit_space_action(
            actor=request.user,
            space=space,
            action="chat.upload_created",
            resource_type="upload_batch",
            resource_id=batch.pk,
            metadata={"source_type": batch.source_type},
        )
        return _batch_response(batch, status_code=201)


class UploadBatchDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def get(self, request, batch_id):
        batch = _visible_batch(request.user, batch_id)
        if batch is None:
            return Response({"detail": "Upload not found."}, status=404)
        takeover = _active_takeover(request.user, batch.space)
        if takeover:
            audit_space_action(
                actor=request.user,
                space=batch.space,
                action="chat.upload_viewed",
                resource_type="upload_batch",
                resource_id=batch.pk,
                metadata={"takeover_id": takeover.pk},
            )
        return _batch_response(batch)

    @transaction.atomic
    def delete(self, request, batch_id):
        batch = _visible_batch(request.user, batch_id, lock=True)
        if batch is None:
            return Response({"detail": "Upload not found."}, status=404)
        if batch.space.status != Space.Status.ACTIVE:
            return _read_only_response()
        try:
            result = revoke_upload(batch, actor=request.user)
        except PermissionError as error:
            return Response({"detail": str(error)}, status=403)
        except RevokeRejected as error:
            return Response({"detail": str(error)}, status=409)
        audit_space_action(
            actor=request.user,
            space=batch.space,
            action="chat.upload_revoked",
            resource_type="upload_batch",
            resource_id=batch_id,
            metadata=result,
        )
        return Response(status=204)

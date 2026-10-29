from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from chat_ingestion.models import UploadBatch
from chat_ingestion.parsing import parse_archive
from chat_ingestion.serializers import (
    UploadBatchCreateSerializer,
    UploadBatchSerializer,
)
from chat_ingestion.services import (
    ArchiveMismatch,
    ArchiveMissing,
    ArchiveTooLarge,
    UploadTransitionError,
    cancel_upload,
    complete_upload,
    store_archive,
)
from spaces.models import Space, SpaceTakeover
from spaces.services import SpacePermissionService, audit_space_action

CONFLICT_FIELDS = (
    "source_type",
    "source_account_id",
    "archive_sha256",
    "archive_size",
)


def _authorized_space(user, space_id, *, lock=False):
    queryset = Space.objects.all()
    if lock:
        queryset = queryset.select_for_update()
    space = get_object_or_404(queryset, pk=space_id)
    if not SpacePermissionService.can_upload(user, space):
        return None
    return space


def _visible_batch(user, batch_id, *, lock=False):
    queryset = UploadBatch.objects.all()
    if lock:
        # select_related plus FOR UPDATE is unsupported on MariaDB, so the
        # space row is fetched lazily instead of locked through the join.
        queryset = queryset.select_for_update()
    else:
        queryset = queryset.select_related("space")
    batch = get_object_or_404(queryset, pk=batch_id)
    if not SpacePermissionService.can_read(user, batch.space):
        return None
    return batch


def _active_takeover(user, space):
    if not getattr(user, "is_staff", False):
        return None
    return SpaceTakeover.objects.filter(
        space=space, admin=user, active=True
    ).first()


def _can_operate_batch(user, batch):
    if getattr(user, "is_staff", False):
        return SpacePermissionService.has_active_takeover(
            user, batch.space
        )
    membership = SpacePermissionService.membership(user, batch.space)
    if not SpacePermissionService.can_write(membership):
        return False
    return (
        user.pk == batch.uploaded_by_id
        or SpacePermissionService.can_manage(membership)
    )


def _idempotency_conflicts(batch, values):
    for field in CONFLICT_FIELDS:
        declared = values.get(field)
        if field in ("source_account_id", "archive_sha256") and not declared:
            # Optional values that the retry did not send never conflict.
            continue
        if field == "archive_size" and declared is None:
            continue
        stored = getattr(batch, field)
        if field == "archive_sha256":
            declared = declared.lower()
            stored = (stored or "").lower()
        if stored != declared:
            return True
    return False


def _read_only_response():
    return Response({"detail": "Archived spaces are read-only."}, status=409)


def _batch_response(batch, status_code=200):
    return Response(
        {"data": UploadBatchSerializer(batch).data}, status=status_code
    )


class UploadBatchCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, space_id):
        # Locking the space serializes batch creation for the same space, so
        # the idempotency filter/create pair cannot race on the unique key.
        space = _authorized_space(request.user, space_id, lock=True)
        if space is None:
            return Response({"detail": "Space not found."}, status=404)
        serializer = UploadBatchCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
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
            return _batch_response(batch)
        batch = UploadBatch.objects.create(
            **lookup,
            source_type=values["source_type"],
            source_account_id=values.get("source_account_id") or "",
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


class UploadBatchArchiveAPIView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    @transaction.atomic
    def put(self, request, batch_id):
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
            return Response({"detail": str(error)}, status=413)
        except ArchiveMismatch as error:
            return Response({"detail": str(error)}, status=409)
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
        batch = parse_archive(batch)
        takeover = _active_takeover(request.user, batch.space)
        audit_space_action(
            actor=request.user,
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
                "takeover_id": takeover.pk if takeover else None,
            },
        )
        if batch.status == UploadBatch.Status.FAILED:
            return Response(
                {
                    "detail": batch.error_message,
                    "data": UploadBatchSerializer(batch).data,
                },
                status=422,
            )
        return _batch_response(batch)


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

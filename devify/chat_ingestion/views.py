from django.conf import settings
from django.db import transaction
from django.db.models import Count
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import DesktopDevice
from accounts.utils import default_device_label
from chat_analysis.models import AnalysisJob, EventNote
from chat_domain.models import MessageOrigin, MessagePart
from chat_ingestion.models import UploadBatch, UploadItem
from chat_ingestion.serializers import (
    UploadBatchCreateSerializer,
    UploadBatchSerializer,
    UploadItemSerializer,
)
from chat_ingestion.services import (
    ArchiveMismatch,
    ArchiveMissing,
    ArchiveTooLarge,
    RevokeRejected,
    UploadTransitionError,
    cancel_upload,
    complete_upload,
    revoke_upload,
    store_archive,
    transition_batch,
)
from chat_ingestion.tasks import (
    dispatch_parse_chat_upload,
    parse_chat_upload_task,
)
from chat_sources.models import SourceImport
from chat_sources.services import get_or_create_upload_source
from spaces.models import Space, SpaceTakeover
from spaces.services import (
    SpacePermissionService,
    audit_space_action,
    check_storage_quota,
)

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


def _authorized_space_for_read(user, space_id):
    space = get_object_or_404(Space, pk=space_id)
    if not SpacePermissionService.can_read(user, space):
        return None, None
    takeover = None
    if getattr(user, "is_staff", False):
        takeover = SpaceTakeover.objects.filter(
            space=space, admin=user, active=True
        ).first()
    return space, takeover


def _visible_batch(user, batch_id, *, lock=False):
    queryset = UploadBatch.objects.all()
    if lock:
        # select_related plus FOR UPDATE is unsupported on MariaDB, so the
        # space row is fetched lazily instead of locked through the join.
        queryset = queryset.select_for_update()
    else:
        queryset = queryset.select_related("space", "source")
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
        return SpacePermissionService.has_active_takeover(user, batch.space)
    membership = SpacePermissionService.membership(user, batch.space)
    if not SpacePermissionService.can_write(membership):
        return False
    return (
        user.pk == batch.uploaded_by_id
        or SpacePermissionService.can_manage(membership)
    )


def _conversation_counts(batches):
    """Count the distinct conversations each batch contributed to.

    Counting through the serializer's relations would multiply the origin and
    part joins and took tens of seconds on a real space, so the page is counted
    in one grouped query instead.
    """
    batch_ids = [batch.pk for batch in batches]
    if not batch_ids:
        return {}
    return dict(
        MessageOrigin.objects.filter(upload_item__batch_id__in=batch_ids)
        .values_list("upload_item__batch_id")
        .annotate(total=Count("message__conversation_id", distinct=True))
    )


def _image_counts(batches):
    """Count distinct image parts each upload batch contributed."""
    batch_ids = [batch.pk for batch in batches]
    if not batch_ids:
        return {}
    return dict(
        MessagePart.objects.filter(
            upload_item__batch_id__in=batch_ids,
            kind=MessagePart.Kind.IMAGE,
        )
        .values_list("upload_item__batch_id")
        .annotate(total=Count("id", distinct=True))
    )


def _analysis_summaries(batches):
    """Summarise the analysis jobs and events each batch contributed.

    A reused job (same conversation digest uploaded again) can be linked to
    several batches, so event counts are assigned to every linked batch.
    """
    batch_ids = [batch.pk for batch in batches]
    if not batch_ids:
        return {}
    summaries = {
        batch_id: {
            "job_ids": set(),
            "states": [],
            "retried": False,
            "started_at": None,
            "finished_at": None,
        }
        for batch_id in batch_ids
    }
    job_batches = {}
    rows = AnalysisJob.objects.filter(upload_batches__id__in=batch_ids).values(
        "id",
        "state",
        "attempts",
        "created_at",
        "updated_at",
        "upload_batches__id",
    )
    for row in rows:
        batch_id = row["upload_batches__id"]
        summary = summaries[batch_id]
        summary["job_ids"].add(row["id"])
        summary["states"].append(row["state"])
        if row["attempts"] > 1 and row["state"] in (
            AnalysisJob.State.READY,
            AnalysisJob.State.PARTIAL,
        ):
            summary["retried"] = True
        started = summary["started_at"]
        if started is None or row["created_at"] < started:
            summary["started_at"] = row["created_at"]
        finished = summary["finished_at"]
        if finished is None or row["updated_at"] > finished:
            summary["finished_at"] = row["updated_at"]
        job_batches.setdefault(row["id"], set()).add(batch_id)

    events_by_batch = {batch_id: set() for batch_id in batch_ids}
    job_ids = list(job_batches)
    if job_ids:
        event_rows = (
            EventNote.objects.filter(note__analysis_job_id__in=job_ids)
            .values("note__analysis_job_id", "event_id")
            .distinct()
        )
        for row in event_rows:
            for batch_id in job_batches.get(row["note__analysis_job_id"], ()):
                events_by_batch[batch_id].add(row["event_id"])

    result = {}
    for batch_id, summary in summaries.items():
        states = summary["states"]
        running = any(
            state in (AnalysisJob.State.QUEUED, AnalysisJob.State.RUNNING)
            for state in states
        )
        failed = any(
            state in (AnalysisJob.State.FAILED, AnalysisJob.State.CANCELLED)
            for state in states
        )
        partial = any(state == AnalysisJob.State.PARTIAL for state in states)
        if running:
            state = "running"
        elif failed:
            state = "failed"
        elif partial:
            state = "partial"
        elif states:
            state = "ready"
        else:
            state = ""
        started = summary["started_at"]
        finished = summary["finished_at"]
        duration_seconds = None
        if started and finished and not running:
            duration_seconds = max(
                0, round((finished - started).total_seconds())
            )
        result[batch_id] = {
            "state": state,
            "job_count": len(summary["job_ids"]),
            "event_count": len(events_by_batch[batch_id]),
            "running": running,
            "failed": failed,
            "partial": partial,
            "retried": summary["retried"],
            "duration_seconds": duration_seconds,
        }
    return result


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


def _resolve_upload_device(request, values):
    """Bind an upload to its desktop device and refresh that device row.

    The access token may already carry a device id. Newer clients also send
    one explicitly together with their platform, which lets an upload register
    the device without a separate round trip. Returns ``(device_id, platform)``
    and uses ``None`` as the device id when the device was revoked.
    """
    auth = request.auth or {}
    device_id = (
        values.get("device_id") or auth.get("device_id") or ""
    ).strip()[:100]
    platform = (values.get("platform") or "").strip()[:40]
    label = (values.get("device_label") or "").strip()[:120]
    if not device_id:
        return "", platform
    device = DesktopDevice.objects.filter(
        user=request.user, device_id=device_id
    ).first()
    if device is not None:
        if device.status == DesktopDevice.Status.REVOKED:
            return None, platform
        device.label = (
            label
            or device.label
            or default_device_label(platform or device.platform)
        )
        device.platform = platform or device.platform
        device.status = DesktopDevice.Status.ACTIVE
        device.revoked_at = None
        device.last_seen_at = timezone.now()
        device.save(
            update_fields=(
                "label",
                "platform",
                "status",
                "revoked_at",
                "last_seen_at",
            )
        )
    else:
        DesktopDevice.objects.create(
            user=request.user,
            device_id=device_id,
            label=label or default_device_label(platform),
            platform=platform,
            status=DesktopDevice.Status.ACTIVE,
            last_seen_at=timezone.now(),
        )
    return device_id, platform


def _enqueue_parse(batch):
    if batch.source_id and batch.source_import_id is None:
        batch.source_import = SourceImport.objects.create(
            space=batch.space,
            source=batch.source,
            initiated_by=batch.uploaded_by,
        )
        batch.save(update_fields=("source_import", "updated_at"))

    def dispatch():
        if getattr(settings, "CHAT_UPLOAD_PARSE_INLINE", False):
            return parse_chat_upload_task.run(batch.pk)
        return dispatch_parse_chat_upload(batch)

    if getattr(settings, "CHAT_UPLOAD_PARSE_INLINE", False):
        return dispatch()
    transaction.on_commit(dispatch)
    return None


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
        # Locking the space serializes batch creation for the same space, so
        # the idempotency filter/create pair cannot race on the unique key.
        space = _authorized_space(request.user, space_id, lock=True)
        if space is None:
            return Response({"detail": "Space not found."}, status=404)
        serializer = UploadBatchCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        quota_error = check_storage_quota(space, values.get("archive_size"))
        if quota_error:
            return Response({"detail": quota_error}, status=413)
        source = get_or_create_upload_source(
            space=space,
            actor=request.user,
            channel_type=values["source_type"],
            account_key=values.get("source_account_id", ""),
        )
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


class UploadBatchItemDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, batch_id, item_id):
        batch = _visible_batch(request.user, batch_id)
        if batch is None:
            return Response({"detail": "Upload not found."}, status=404)
        item = get_object_or_404(UploadItem, batch=batch, pk=item_id)
        return Response({"data": UploadItemSerializer(item).data})


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
                batch, UploadBatch.Status.UPLOADING, error_message=""
            )
        except UploadTransitionError as error:
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

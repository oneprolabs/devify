import hashlib
import io
import json
import os
import warnings
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from PIL import Image, UnidentifiedImageError
from rest_framework import serializers
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import JSONParser, MultiPartParser
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

from feedback.models import Feedback, FeedbackAttachment
from feedback.serializers import (
    CreateFeedbackSerializer,
    FeedbackSerializer,
    UpdateFeedbackSerializer,
)


class FeedbackThrottle(UserRateThrottle):
    rate = "30/hour"


class FeedbackPagination(PageNumberPagination):
    page_size = 20


def visible_reports(request, *, admin=False):
    reports = Feedback.objects.select_related("user").prefetch_related(
        "attachments"
    )
    return reports if admin else reports.filter(user=request.user)


def validated_images(files):
    if len(files) > 3:
        raise serializers.ValidationError("最多上传 3 张截图。")
    images = []
    for upload in files:
        if upload.size > 3 * 1024 * 1024:
            raise serializers.ValidationError("每张截图不得超过 3 MB。")
        raw = upload.read()
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(io.BytesIO(raw)) as image:
                    if (
                        image.format not in {"PNG", "JPEG"}
                        or image.width * image.height > 16000000
                    ):
                        raise serializers.ValidationError(
                            "仅支持 1600 万像素以内的 PNG/JPEG。"
                        )
                    image.load()
                    # Strip metadata, appended data and original file names.
                    output = io.BytesIO()
                    image.convert("RGB").save(output, format="PNG")
        except (
            UnidentifiedImageError,
            OSError,
            ValueError,
            Image.DecompressionBombWarning,
            Image.DecompressionBombError,
        ):
            raise serializers.ValidationError("截图不是有效的 PNG/JPEG。")
        if output.tell() > 5 * 1024 * 1024:
            raise serializers.ValidationError("截图处理后过大，请裁剪后上传。")
        images.append((hashlib.sha256(raw).hexdigest(), output.getvalue()))
    return images


class FeedbackList(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser]
    throttle_classes = [FeedbackThrottle]

    def get(self, request):
        pager = FeedbackPagination()
        rows = pager.paginate_queryset(visible_reports(request), request)
        return pager.get_paginated_response(
            FeedbackSerializer(rows, many=True).data
        )

    def post(self, request):
        if int(request.META.get("CONTENT_LENGTH") or 0) > 10 * 1024 * 1024:
            return Response(
                {"detail": "反馈附件总大小不得超过 10 MB。"}, status=413
            )
        raw = request.data.get("payload", "")
        if not isinstance(raw, str) or len(raw.encode()) > 512 * 1024:
            raise serializers.ValidationError("诊断内容不得超过 512 KB。")
        try:
            payload = json.loads(raw)
        except (ValueError, TypeError, RecursionError):
            raise serializers.ValidationError("反馈数据格式无效。")
        serializer = CreateFeedbackSerializer(data=payload)
        serializer.is_valid(raise_exception=True)
        images = validated_images(request.FILES.getlist("screenshots"))
        # Identical validated content is required for every replay.
        canonical = json.dumps(
            serializer.data, sort_keys=True, ensure_ascii=False
        )
        digest = hashlib.sha256(
            (canonical + "".join(item[0] for item in images)).encode()
        ).hexdigest()
        paths = []
        try:
            with transaction.atomic():
                values = dict(serializer.validated_data)
                if "diagnostics" in values:
                    values["diagnostics"] = serializer.data["diagnostics"]
                report = Feedback.objects.create(
                    fingerprint=digest,
                    user=request.user,
                    **values,
                )
                for _, content in images:
                    attachment = FeedbackAttachment.objects.create(
                        feedback=report,
                        mime_type="image/png",
                        size=len(content),
                    )
                    path = attachment.path
                    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                    paths.append(path)
                    with os.fdopen(
                        os.open(
                            path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600
                        ),
                        "wb",
                    ) as stream:
                        stream.write(content)
        except IntegrityError:
            for path in paths:
                path.unlink(missing_ok=True)
            report = Feedback.objects.get(
                user=request.user,
                client_id=serializer.validated_data["client_id"],
            )
            if report.fingerprint != digest:
                return Response(
                    {"detail": "该提交编号已用于其他内容，请新建反馈。"},
                    status=409,
                )
            return Response(FeedbackSerializer(report).data)
        except Exception:
            for path in paths:
                path.unlink(missing_ok=True)
            raise
        return Response(FeedbackSerializer(report).data, status=201)


class FeedbackDetail(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, report_id):
        return Response(
            FeedbackSerializer(
                get_object_or_404(visible_reports(request), pk=report_id)
            ).data
        )


class AttachmentDownload(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, report_id, attachment_id):
        report = get_object_or_404(
            visible_reports(request, admin=request.user.is_staff), pk=report_id
        )
        attachment = get_object_or_404(report.attachments, pk=attachment_id)
        if (
            attachment.expired
            or report.created_at < timezone.now() - timedelta(days=30)
        ):
            return Response({"detail": "附件已过期。"}, status=410)
        try:
            stream = attachment.path.open("rb")
        except FileNotFoundError:
            return Response({"detail": "附件已过期。"}, status=410)
        response = FileResponse(
            stream,
            content_type=attachment.mime_type,
            as_attachment=True,
            filename=f"screenshot-{attachment.id}.png",
        )
        response["Cache-Control"] = "private, no-store"
        response["X-Content-Type-Options"] = "nosniff"
        return response


class AdminFeedbackList(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        rows = visible_reports(request, admin=True)
        if request.query_params.get("status"):
            rows = rows.filter(status=request.query_params["status"])
        pager = FeedbackPagination()
        page = pager.paginate_queryset(rows, request)
        return pager.get_paginated_response(
            FeedbackSerializer(page, many=True).data
        )


class AdminFeedbackDetail(APIView):
    permission_classes = [IsAdminUser]
    parser_classes = [JSONParser]

    def patch(self, request, report_id):
        report = get_object_or_404(
            visible_reports(request, admin=True), pk=report_id
        )
        serializer = UpdateFeedbackSerializer(
            report, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(FeedbackSerializer(report).data)

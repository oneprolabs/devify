"""Authenticated, space-scoped conversation summary endpoints."""

import json
import uuid
from urllib.parse import urlsplit

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils.cache import patch_vary_headers
from django.utils.http import parse_etags
from rest_framework.exceptions import (
    NotFound,
    PermissionDenied,
    ValidationError,
)
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from billing.entitlements import can_use_chat_summary
from chat_analysis.models import ChatSummary
from chat_analysis.summaries.configuration import build_configuration
from chat_analysis.summaries.prompts import (
    current_snapshot,
    load_config,
    sha256,
)
from chat_analysis.summaries.serializers import SummaryCreate, SummaryOutput
from chat_analysis.summaries.services import (
    dispatch,
    expire_stale_summaries,
    summary_input_hash,
)
from spaces.models import Space
from spaces.services import SpacePermissionService, check_daily_ai_quota


def summary_space(user, space_id, *, write=False):
    """Resolve a readable or writable space for an active summary user."""
    space = get_object_or_404(Space, pk=space_id)
    allowed = (
        SpacePermissionService.can_upload(user, space)
        if write
        else SpacePermissionService.can_read(user, space)
    )
    if not allowed:
        raise NotFound("Space not found.")
    if not can_use_chat_summary(user):
        raise PermissionDenied("当前账号未开通聊天总结。")
    return space


def summary_server_origin(request):
    """Recover the HTTPS origin when a same-host proxy reports HTTP."""
    origin = request.build_absolute_uri("/").rstrip("/")
    if request.is_secure():
        return origin

    try:
        frontend = urlsplit(settings.FRONTEND_URL)
    except ValueError:
        return origin

    if frontend.scheme == "https" and (
        frontend.netloc.lower() == request.get_host().lower()
    ):
        return f"https://{frontend.netloc}"
    return origin


class SummaryConfiguration(APIView):
    """Initialize a desktop catalog or revalidate its scoped ETag."""

    permission_classes = [IsAuthenticated]

    def get(self, request, space_id):
        """Check access before returning either configuration or 304."""
        space = summary_space(request.user, space_id)
        if request.query_params.get("schema_version") != "1":
            raise ValidationError("Unsupported summary configuration schema.")
        data = build_configuration(
            request.user, space, summary_server_origin(request)
        )
        digest = sha256(json.dumps(data, sort_keys=True, ensure_ascii=False))
        etag = f'"{digest}"'
        candidates = parse_etags(request.headers.get("If-None-Match", ""))
        unchanged = "*" in candidates or etag in [
            value.removeprefix("W/") for value in candidates
        ]
        response = Response(
            None if unchanged else {"data": data},
            status=304 if unchanged else 200,
        )
        response["ETag"] = etag
        response["Cache-Control"] = "private, no-cache"
        patch_vary_headers(response, ("Authorization", "Cookie"))
        return response


class SummaryPagination(PageNumberPagination):
    """Bound the number of user-owned snapshots in one response."""

    page_size = 20
    max_page_size = 50


class SummaryList(APIView):
    """List and admit immutable user-owned summary requests."""

    permission_classes = [IsAuthenticated]

    def get(self, request, space_id):
        """Paginate snapshots belonging to the current user and space."""
        space = summary_space(request.user, space_id)
        expire_stale_summaries()
        rows = (
            ChatSummary.objects.filter(space=space, created_by=request.user)
            .defer("input_messages")
            .order_by("-created_at", "-id")
        )
        for field in [
            "platform",
            "source_namespace",
            "source_conversation_id",
        ]:
            value = request.query_params.get(field)
            if value:
                rows = rows.filter(**{field: value})
        paginator = SummaryPagination()
        page = paginator.paginate_queryset(rows, request, view=self)
        return Response(
            {
                "data": {
                    "list": SummaryOutput(page, many=True).data,
                    "pagination": {
                        "total": paginator.page.paginator.count,
                        "page": paginator.page.number,
                        "next": paginator.get_next_link(),
                    },
                }
            }
        )

    @transaction.atomic
    def post(self, request, space_id):
        """Deduplicate before admitting and pinning a new summary task."""
        space = summary_space(request.user, space_id, write=True)
        data = SummaryCreate(data=request.data)
        data.is_valid(raise_exception=True)
        values = data.validated_data.copy()
        # Serialize admission and request-key retries for this user.
        get_user_model().objects.select_for_update().get(pk=request.user.pk)
        digest = summary_input_hash(values)
        existing = ChatSummary.objects.filter(
            space=space,
            created_by=request.user,
            request_key=values["request_key"],
        ).first()
        if existing:
            if existing.input_hash != digest:
                return Response(
                    {"detail": "同一请求已使用不同内容，请重新提交。"},
                    status=409,
                )
            return Response({"data": SummaryOutput(existing).data})
        config = load_config()
        try:
            snapshot = current_snapshot(config, values.pop("scenario", None))
        except ValueError as error:
            raise ValidationError({"scenario": str(error)}) from error
        instructions = values.pop("instructions", "")
        scenario = config["scenarios"][snapshot["scenario"]]
        if scenario.get("requires_instructions") and not instructions:
            raise ValidationError({"instructions": "请描述希望得到什么内容。"})
        snapshot["user_instructions"] = instructions
        version = values.pop("prompt_version", snapshot["version"])
        prompt_digest = values.pop("prompt_digest", snapshot["sha256"])
        if (version, prompt_digest) != (
            snapshot["version"],
            snapshot["sha256"],
        ):
            return Response(
                {
                    "detail": "总结配置已更新，请刷新配置后重新提交。",
                    "error_code": "summary_config_changed",
                },
                status=409,
            )
        expire_stale_summaries()
        if (
            ChatSummary.objects.filter(
                created_by=request.user, status__in=["queued", "running"]
            ).count()
            >= 3
        ):
            return Response(
                {"detail": "已有 3 个总结正在处理，请稍后再试。"}, status=429
            )
        quota_error = check_daily_ai_quota(space)
        if quota_error:
            return Response({"detail": quota_error}, status=429)
        messages = values.pop("messages")
        sessions = {}
        for item in messages:
            entry = sessions.setdefault(
                item["username"],
                {
                    "username": item["username"],
                    "display": item["display"],
                    "messages": 0,
                },
            )
            entry["messages"] += 1
        summary = ChatSummary.objects.create(
            space=space,
            created_by=request.user,
            input_hash=digest,
            prompt_snapshot=snapshot,
            input_messages=messages,
            sessions=list(sessions.values()),
            message_count=len(messages),
            **values,
        )
        transaction.on_commit(lambda: dispatch(summary))
        return Response({"data": SummaryOutput(summary).data}, status=202)


class SummaryDetail(APIView):
    """Read, delete or retry the original immutable summary intent."""

    permission_classes = [IsAuthenticated]

    def _record(self, request, space_id, summary_id, *, write=False):
        space = summary_space(request.user, space_id, write=write)
        expire_stale_summaries()
        return get_object_or_404(
            ChatSummary, pk=summary_id, space=space, created_by=request.user
        )

    def get(self, request, space_id, summary_id):
        """Read one authorized snapshot without changing its intent."""
        return Response(
            {
                "data": SummaryOutput(
                    self._record(request, space_id, summary_id)
                ).data
            }
        )

    def delete(self, request, space_id, summary_id):
        """Delete only terminal summaries owned by the current user."""
        record = self._record(request, space_id, summary_id, write=True)
        if record.status in {"queued", "running"}:
            raise ValidationError("请等待总结结束后再删除。")
        record.delete()
        return Response(status=204)

    @transaction.atomic
    def post(self, request, space_id, summary_id):
        """Retry the stored intent with a fresh dispatch token."""
        get_user_model().objects.select_for_update().get(pk=request.user.pk)
        self._record(request, space_id, summary_id, write=True)
        record = ChatSummary.objects.select_for_update().get(pk=summary_id)
        if record.status != "failed":
            return Response({"data": SummaryOutput(record).data})
        if (
            ChatSummary.objects.filter(
                created_by=request.user, status__in=["queued", "running"]
            ).count()
            >= 3
        ):
            return Response(
                {"detail": "已有 3 个总结正在处理，请稍后再试。"}, status=429
            )
        record.status, record.error, record.dispatch_token = (
            "queued",
            "",
            uuid.uuid4(),
        )
        record.save(
            update_fields=["status", "error", "dispatch_token", "updated_at"]
        )
        transaction.on_commit(lambda: dispatch(record))
        return Response({"data": SummaryOutput(record).data}, status=202)

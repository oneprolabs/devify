"""Space workflow configuration and quota endpoints."""

from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from spaces.models import (
    Space,
    SpaceMembership,
    SpaceQuota,
    SpaceWorkflowConfig,
)
from spaces.serializers import (
    SpaceQuotaSerializer,
    SpaceQuotaUpdateSerializer,
    SpaceWorkflowConfigSerializer,
    SpaceWorkflowConfigUpdateSerializer,
)
from spaces.services import SpacePermissionService, audit_space_action


class SpaceWorkflowConfigAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, space_id):
        space = get_object_or_404(Space, pk=space_id)
        if not SpacePermissionService.can_read(request.user, space):
            return Response({"detail": "Space not found."}, status=404)
        config, _ = SpaceWorkflowConfig.objects.get_or_create(space=space)
        return Response({"data": SpaceWorkflowConfigSerializer(config).data})

    @transaction.atomic
    def patch(self, request, space_id):
        space = get_object_or_404(Space, pk=space_id)
        membership = SpacePermissionService.membership(request.user, space)
        can_manage = SpacePermissionService.can_manage(membership) or (
            request.user.is_staff
            and SpacePermissionService.has_active_takeover(request.user, space)
        )
        if not can_manage:
            return Response(
                {
                    "detail": (
                        "Space workflow configuration permission required."
                    )
                },
                status=403,
            )
        (
            config,
            _,
        ) = SpaceWorkflowConfig.objects.select_for_update().get_or_create(
            space=space
        )
        serializer = SpaceWorkflowConfigUpdateSerializer(
            data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        for field, value in serializer.validated_data.items():
            setattr(config, field, value)
        config.version += 1
        config.updated_by = request.user
        config.save()
        audit_space_action(
            actor=request.user,
            space=space,
            action="space.workflow_config_updated",
            resource_type="workflow_config",
            metadata={"version": config.version},
        )
        return Response({"data": SpaceWorkflowConfigSerializer(config).data})


class SpaceQuotaUsageAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, space_id):
        space = get_object_or_404(Space, pk=space_id)
        if not SpacePermissionService.can_read(request.user, space):
            return Response({"detail": "Space not found."}, status=404)
        from django.db.models import Sum
        from django.utils import timezone

        from chat_analysis.models import ChatSummary, QuestionAnswer
        from chat_domain.models import Conversation, Message, MessagePart
        from chat_ingestion.models import UploadBatch

        quota, _ = SpaceQuota.objects.get_or_create(space=space)
        member_count = space.memberships.filter(
            status=SpaceMembership.Status.ACTIVE
        ).count()
        storage_used = (
            UploadBatch.objects.filter(space=space)
            .exclude(status=UploadBatch.Status.CANCELLED)
            .aggregate(total=Sum("archive_size"))["total"]
            or 0
        )
        conversation_count = Conversation.objects.filter(space=space).count()
        message_count = Message.objects.filter(
            conversation__space=space
        ).count()
        media_count = MessagePart.objects.filter(
            message__conversation__space=space,
            kind__in=(
                MessagePart.Kind.IMAGE,
                MessagePart.Kind.VIDEO,
                MessagePart.Kind.AUDIO,
                MessagePart.Kind.FILE,
            ),
        ).count()
        day_start = timezone.localtime(timezone.now()).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        ai_calls = QuestionAnswer.objects.filter(
            space=space, created_at__gte=day_start
        ).count()
        ai_calls += ChatSummary.objects.filter(
            space=space, created_at__gte=day_start
        ).count()
        return Response(
            {
                "data": {
                    "quota": SpaceQuotaSerializer(quota).data,
                    "usage": {
                        "member_count": member_count,
                        "storage_used_bytes": storage_used,
                        "conversation_count": conversation_count,
                        "message_count": message_count,
                        "media_count": media_count,
                        "daily_ai_calls_used": ai_calls,
                    },
                }
            }
        )


class SpaceQuotaAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, space_id):
        space = get_object_or_404(Space, pk=space_id)
        if not SpacePermissionService.can_read(request.user, space):
            return Response({"detail": "Space not found."}, status=404)
        quota, _ = SpaceQuota.objects.get_or_create(space=space)
        return Response({"data": SpaceQuotaSerializer(quota).data})

    @transaction.atomic
    def patch(self, request, space_id):
        space = get_object_or_404(Space, pk=space_id)
        membership = SpacePermissionService.membership(request.user, space)
        can_manage = SpacePermissionService.can_manage(membership) or (
            request.user.is_staff
            and SpacePermissionService.has_active_takeover(request.user, space)
        )
        if not can_manage:
            return Response(
                {"detail": "Space quota permission required."}, status=403
            )
        quota, _ = SpaceQuota.objects.select_for_update().get_or_create(
            space=space
        )
        serializer = SpaceQuotaUpdateSerializer(
            data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        for field, value in serializer.validated_data.items():
            setattr(quota, field, value)
        quota.updated_by = request.user
        quota.save()
        audit_space_action(
            actor=request.user,
            space=space,
            action="space.quota_updated",
            resource_type="quota",
            metadata=serializer.validated_data,
        )
        return Response({"data": SpaceQuotaSerializer(quota).data})

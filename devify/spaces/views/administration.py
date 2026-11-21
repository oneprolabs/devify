"""Space takeover, policy, and audit endpoints."""

from django.contrib.auth import get_user_model
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from spaces.models import Space, SpaceAuditLog, SpaceTakeover
from spaces.serializers import SpacePolicySerializer, TakeoverSerializer
from spaces.services import (
    SpacePermissionService,
    audit_space_action,
    get_space_policy,
    takeover_space,
)


class SpaceTakeoverAPIView(APIView):
    permission_classes = [IsAdminUser]

    @transaction.atomic
    def post(self, request, space_id):
        space = get_object_or_404(
            Space.objects.select_for_update(), pk=space_id
        )
        serializer = TakeoverSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        owner_user = None
        owner_id = serializer.validated_data.get("owner_user_id")
        if owner_id:
            owner_user = get_object_or_404(get_user_model(), pk=owner_id)
            if space.owner_id or space.kind == Space.Kind.PERSONAL:
                return Response(
                    {
                        "detail": "Owner assignment requires an ownerless "
                        "team space."
                    },
                    status=409,
                )
        if SpaceTakeover.objects.filter(
            space=space, admin=request.user, active=True
        ).exists():
            return Response({"detail": "Takeover already active."}, status=409)
        takeover = takeover_space(
            admin=request.user,
            space=space,
            reason=serializer.validated_data["reason"],
            owner_user=owner_user,
        )
        return Response(
            {
                "data": {
                    "id": takeover.id,
                    "space_id": space.id,
                    "active": True,
                }
            },
            status=201,
        )

    @transaction.atomic
    def delete(self, request, space_id):
        takeover = (
            SpaceTakeover.objects.filter(
                space_id=space_id,
                admin=request.user,
                active=True,
            )
            .order_by("-started_at")
            .first()
        )
        if not takeover:
            return Response(
                {"detail": "Active takeover not found."}, status=404
            )
        takeover.active = False
        takeover.ended_at = timezone.now()
        takeover.save(update_fields=("active", "ended_at"))
        audit_space_action(
            actor=request.user,
            space=takeover.space,
            action="space.takeover_ended",
        )
        return Response(status=204)


class SpacePolicyAPIView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        policy = get_space_policy()
        return Response(
            {
                "data": {
                    "allow_user_create_spaces": (
                        policy.allow_user_create_spaces
                    ),
                    "max_invited_users": policy.max_invited_users,
                }
            }
        )

    @transaction.atomic
    def patch(self, request):
        serializer = SpacePolicySerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        policy = get_space_policy()
        for key, value in serializer.validated_data.items():
            setattr(policy, key, value)
        policy.updated_by = request.user
        policy.save()
        SpaceAuditLog.objects.create(
            actor=request.user,
            action="space.policy.updated",
            metadata={
                "allow_user_create_spaces": policy.allow_user_create_spaces,
                "max_invited_users": policy.max_invited_users,
            },
        )
        return self.get(request)


class SpaceAuditLogListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, space_id):
        space = get_object_or_404(Space, pk=space_id)
        if not SpacePermissionService.can_read(request.user, space):
            return Response({"detail": "Space not found."}, status=404)
        logs = SpaceAuditLog.objects.filter(space=space).select_related(
            "actor"
        )
        action = request.query_params.get("action", "").strip()
        if action:
            logs = logs.filter(action=action)
        try:
            page = max(int(request.query_params.get("page", 1)), 1)
        except (TypeError, ValueError):
            page = 1
        try:
            page_size = min(
                max(int(request.query_params.get("page_size", 50)), 1), 100
            )
        except (TypeError, ValueError):
            page_size = 50
        total = logs.count()
        start = (page - 1) * page_size
        data = [
            {
                "id": log.pk,
                "actor_id": log.actor_id,
                "actor": log.actor.get_username() if log.actor else None,
                "action": log.action,
                "resource_type": log.resource_type,
                "resource_id": log.resource_id,
                "metadata": log.metadata,
                "created_at": log.created_at,
            }
            for log in logs[start : start + page_size]
        ]
        return Response(
            {
                "data": {
                    "list": data,
                    "pagination": {
                        "total": total,
                        "page": page,
                        "page_size": page_size,
                        "has_next": start + page_size < total,
                        "has_previous": page > 1,
                    },
                }
            }
        )

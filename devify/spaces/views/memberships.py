"""Space invitation, membership, and ownership endpoints."""

from django.contrib.auth import get_user_model
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from spaces.models import Space, SpaceMembership
from spaces.serializers import (
    MemberInviteSerializer,
    MemberRoleSerializer,
    OwnershipTransferSerializer,
)
from spaces.services import (
    SpacePermissionService,
    audit_space_action,
    check_member_quota,
    invite_member,
    transfer_space_ownership,
)


def _space_for_member(request, space_id, *, for_update=False):
    spaces = Space.objects.select_for_update() if for_update else Space.objects
    space = get_object_or_404(spaces, pk=space_id)
    membership = SpacePermissionService.membership(request.user, space)
    if not membership:
        return None, None
    return space, membership


class SpaceInvitationListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        memberships = (
            SpaceMembership.objects.filter(
                user=request.user,
                status=SpaceMembership.Status.INVITED,
            )
            .select_related("space", "invited_by")
            .order_by("space__name", "space_id")
        )
        data = [
            {
                "space_id": membership.space_id,
                "user_id": membership.user_id,
                "space_name": membership.space.name,
                "space_slug": membership.space.slug,
                "role": membership.role,
                "invited_by_id": membership.invited_by_id,
            }
            for membership in memberships
        ]
        return Response({"data": data})


class SpaceMemberListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, space_id):
        space, membership = _space_for_member(request, space_id)
        if not membership:
            return Response({"detail": "Space not found."}, status=404)
        members = SpaceMembership.objects.filter(
            space=space,
            status=SpaceMembership.Status.ACTIVE,
        ).select_related("user")
        data = [
            {
                "user_id": item.user_id,
                "username": item.user.get_username(),
                "role": item.role,
                "status": item.status,
            }
            for item in members
        ]
        return Response({"data": data})

    @transaction.atomic
    def post(self, request, space_id):
        space, membership = _space_for_member(
            request, space_id, for_update=True
        )
        if not SpacePermissionService.can_manage(membership):
            return Response(
                {"detail": "Space manager permission required."}, status=403
            )
        if space.status != Space.Status.ACTIVE:
            return Response(
                {"detail": "Archived spaces are read-only."}, status=409
            )
        if space.kind == Space.Kind.PERSONAL:
            return Response(
                {"detail": "Personal spaces cannot invite members."},
                status=409,
            )
        quota_error = check_member_quota(space)
        if quota_error:
            return Response({"detail": quota_error}, status=409)
        serializer = MemberInviteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user_model = get_user_model()
        user = get_object_or_404(
            user_model,
            pk=serializer.validated_data["user_id"],
        )
        try:
            invited = invite_member(
                actor=request.user,
                space=space,
                user=user,
                role=serializer.validated_data["role"],
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=409)
        return Response(
            {
                "data": {
                    "user_id": invited.user_id,
                    "role": invited.role,
                    "status": invited.status,
                }
            },
            status=201,
        )


class SpaceMemberAcceptAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, space_id, user_id):
        space = get_object_or_404(
            Space.objects.select_for_update(), pk=space_id
        )
        membership = SpaceMembership.objects.filter(
            space=space,
            user_id=user_id,
        ).first()
        if not membership or (
            membership.status != SpaceMembership.Status.INVITED
        ):
            return Response({"detail": "Invitation not found."}, status=404)
        if membership.user_id != request.user.id:
            return Response(
                {"detail": "Only the invited user can accept."}, status=403
            )
        if space.status != Space.Status.ACTIVE:
            return Response({"detail": "Space is not active."}, status=409)
        membership.status = SpaceMembership.Status.ACTIVE
        membership.joined_at = timezone.now()
        membership.save(update_fields=("status", "joined_at", "updated_at"))
        audit_space_action(
            actor=request.user,
            space=space,
            action="membership.accepted",
            resource_type="user",
            resource_id=request.user.pk,
        )
        return Response(
            {"data": {"user_id": user_id, "status": membership.status}}
        )

    @transaction.atomic
    def delete(self, request, space_id, user_id):
        space = get_object_or_404(Space, pk=space_id)
        membership = SpaceMembership.objects.filter(
            space=space,
            user_id=user_id,
            status=SpaceMembership.Status.INVITED,
        ).first()
        if not membership:
            return Response({"detail": "Invitation not found."}, status=404)
        if membership.user_id != request.user.id:
            return Response(
                {"detail": "Only the invited user can reject."}, status=403
            )
        membership.status = SpaceMembership.Status.REMOVED
        membership.save(update_fields=("status", "updated_at"))
        audit_space_action(
            actor=request.user,
            space=space,
            action="membership.rejected",
            resource_type="user",
            resource_id=request.user.pk,
        )
        return Response(status=204)


class SpaceMemberActionAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def patch(self, request, space_id, user_id):
        space, actor_membership = _space_for_member(
            request, space_id, for_update=True
        )
        if not SpacePermissionService.can_manage(actor_membership):
            return Response(
                {"detail": "Space manager permission required."}, status=403
            )
        if space.status != Space.Status.ACTIVE:
            return Response({"detail": "Space is not active."}, status=409)
        target = get_object_or_404(
            SpaceMembership,
            space=space,
            user_id=user_id,
        )
        serializer = MemberRoleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        role = serializer.validated_data["role"]
        if target.role == SpaceMembership.Role.OWNER and role != target.role:
            return Response(
                {"detail": "Transfer ownership before demotion."}, status=409
            )
        if role == SpaceMembership.Role.OWNER and target.role != role:
            return Response({"detail": "Use ownership transfer."}, status=403)
        target.role = role
        target.save(update_fields=("role", "updated_at"))
        audit_space_action(
            actor=request.user,
            space=space,
            action="membership.role_changed",
            resource_type="user",
            resource_id=user_id,
            metadata={"role": role},
        )
        return Response({"data": {"user_id": user_id, "role": role}})

    @transaction.atomic
    def delete(self, request, space_id, user_id):
        space, actor_membership = _space_for_member(
            request, space_id, for_update=True
        )
        if not actor_membership:
            return Response({"detail": "Space not found."}, status=404)
        if (
            request.user.id != user_id
            and not SpacePermissionService.can_manage(actor_membership)
        ):
            return Response(
                {"detail": "Space manager permission required."}, status=403
            )
        target = get_object_or_404(
            SpaceMembership, space=space, user_id=user_id
        )
        if target.user_id == space.owner_id and request.user.id != user_id:
            return Response({"detail": "Cannot remove the owner."}, status=403)
        if target.user_id == space.personal_owner_id:
            return Response(
                {"detail": "Cannot leave a personal space."}, status=409
            )
        if target.status == SpaceMembership.Status.REMOVED:
            return Response({"detail": "Member not found."}, status=404)
        target.status = SpaceMembership.Status.REMOVED
        target.save(update_fields=("status", "updated_at"))
        if space.owner_id == target.user_id:
            space.owner = None
            space.save(update_fields=("owner", "updated_at"))
        audit_space_action(
            actor=request.user,
            space=space,
            action="membership.removed",
            resource_type="user",
            resource_id=user_id,
        )
        return Response(status=204)


class SpaceOwnershipAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, space_id):
        space = get_object_or_404(Space, pk=space_id)
        actor_membership = SpacePermissionService.membership(
            request.user, space
        )
        if not actor_membership or actor_membership.role != (
            SpaceMembership.Role.OWNER
        ):
            return Response(
                {"detail": "Space owner permission required."}, status=403
            )
        serializer = OwnershipTransferSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = get_object_or_404(
            get_user_model(), pk=serializer.validated_data["user_id"]
        )
        try:
            transfer_space_ownership(
                actor=request.user, space=space, user=user
            )
        except (PermissionError, ValueError) as exc:
            return Response({"detail": str(exc)}, status=409)
        return Response(
            {"data": {"space_id": space_id, "owner_user_id": user.pk}}
        )

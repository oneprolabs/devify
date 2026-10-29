from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.text import slugify
from rest_framework import status
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from spaces.models import Space, SpaceAuditLog, SpaceMembership, SpaceTakeover
from spaces.serializers import (
    MemberInviteSerializer,
    MemberRoleSerializer,
    OwnershipTransferSerializer,
    SpaceCreateSerializer,
    SpacePolicySerializer,
    SpaceSerializer,
    SpaceUpdateSerializer,
    TakeoverSerializer,
)
from spaces.services import (
    SpacePermissionService,
    audit_space_action,
    get_space_policy,
    invite_member,
    takeover_space,
    transfer_space_ownership,
)


def _serialize_space(space, user):
    serializer = SpaceSerializer(space)
    data = dict(serializer.data)
    membership = SpacePermissionService.membership(user, space)
    data["role"] = membership.role if membership else None
    return data


class SpaceListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        spaces = Space.objects.filter(
            memberships__user=request.user,
            memberships__status=SpaceMembership.Status.ACTIVE,
        ).distinct()
        data = [_serialize_space(space, request.user) for space in spaces]
        return Response({"data": data})

    @transaction.atomic
    def post(self, request):
        serializer = SpaceCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        policy = get_space_policy()
        if not request.user.is_staff and not policy.allow_user_create_spaces:
            return Response(
                {"detail": "Space creation is disabled for this account."},
                status=status.HTTP_403_FORBIDDEN,
            )
        name = serializer.validated_data["name"]
        slug = serializer.validated_data.get("slug") or slugify(name)
        if not slug:
            return Response(
                {"detail": "A valid space slug is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if slug.lower().startswith("personal-"):
            return Response(
                {"detail": "This space slug is reserved."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if Space.objects.filter(slug=slug).exists():
            return Response(
                {"detail": "A space with this slug already exists."},
                status=status.HTTP_409_CONFLICT,
            )
        try:
            with transaction.atomic():
                space = Space.objects.create(
                    name=name,
                    slug=slug,
                    kind=Space.Kind.TEAM,
                    owner=request.user,
                    created_by=request.user,
                )
        except IntegrityError:
            return Response(
                {"detail": "A space with this slug already exists."},
                status=status.HTTP_409_CONFLICT,
            )
        SpaceMembership.objects.create(
            space=space,
            user=request.user,
            role=SpaceMembership.Role.OWNER,
            status=SpaceMembership.Status.ACTIVE,
        )
        audit_space_action(
            actor=request.user,
            space=space,
            action="space.created",
        )
        return Response(
            {"data": _serialize_space(space, request.user)},
            status=status.HTTP_201_CREATED,
        )


class SpaceInvitationListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        memberships = SpaceMembership.objects.filter(
            user=request.user,
            status=SpaceMembership.Status.INVITED,
        ).select_related("space", "invited_by").order_by(
            "space__name", "space_id"
        )
        data = [
            {
                "space_id": membership.space_id,
                "space_name": membership.space.name,
                "space_slug": membership.space.slug,
                "role": membership.role,
                "invited_by_id": membership.invited_by_id,
            }
            for membership in memberships
        ]
        return Response({"data": data})


class SpaceDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, space_id):
        space = Space.objects.filter(
            pk=space_id,
            memberships__user=request.user,
            memberships__status=SpaceMembership.Status.ACTIVE,
        ).first()
        if not space:
            return Response(
                {"detail": "Space not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response({"data": _serialize_space(space, request.user)})

    @transaction.atomic
    def patch(self, request, space_id):
        space, membership = _space_for_member(
            request, space_id, for_update=True
        )
        if not membership:
            return Response({"detail": "Space not found."}, status=404)
        serializer = SpaceUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        changes = serializer.validated_data
        if not changes:
            return Response({"data": _serialize_space(space, request.user)})
        if space.status == Space.Status.SUSPENDED:
            return Response(
                {"detail": "Suspended spaces cannot be changed."}, status=409
            )
        if "name" in changes and not SpacePermissionService.can_manage(
            membership
        ):
            return Response(
                {"detail": "Space manager permission required."}, status=403
            )
        if "status" in changes:
            if space.kind == Space.Kind.PERSONAL:
                return Response(
                    {"detail": "Personal spaces cannot be archived."},
                    status=409,
                )
            if membership.role != SpaceMembership.Role.OWNER:
                return Response(
                    {"detail": "Space owner permission required."}, status=403
                )
        changed_fields = []
        for field, value in changes.items():
            if getattr(space, field) != value:
                setattr(space, field, value)
                changed_fields.append(field)
        if changed_fields:
            space.save(update_fields=tuple(changed_fields) + ("updated_at",))
            audit_space_action(
                actor=request.user,
                space=space,
                action="space.updated",
                metadata={
                    field: getattr(space, field) for field in changed_fields
                },
            )
        return Response({"data": _serialize_space(space, request.user)})


def _space_for_member(request, space_id, *, for_update=False):
    spaces = Space.objects.select_for_update() if for_update else Space.objects
    space = get_object_or_404(spaces, pk=space_id)
    membership = SpacePermissionService.membership(request.user, space)
    if not membership:
        return None, None
    return space, membership


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
                    {"detail": "Owner assignment requires an ownerless "
                               "team space."},
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
            {"data": {
                "id": takeover.id, "space_id": space.id, "active": True,
            }},
            status=201,
        )

    @transaction.atomic
    def delete(self, request, space_id):
        takeover = SpaceTakeover.objects.filter(
            space_id=space_id,
            admin=request.user,
            active=True,
        ).order_by("-started_at").first()
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


class OwnerlessSpaceListAPIView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        spaces = Space.objects.filter(
            kind=Space.Kind.TEAM, owner__isnull=True
        )
        return Response({"data": SpaceSerializer(spaces, many=True).data})


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

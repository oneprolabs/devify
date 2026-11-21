"""Space listing, creation, and lifecycle endpoints."""

from django.db import IntegrityError, transaction
from django.utils.text import slugify
from rest_framework import status
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from spaces.models import Space, SpaceMembership, SpaceTakeover
from spaces.serializers import (
    SpaceCreateSerializer,
    SpaceSerializer,
    SpaceUpdateSerializer,
)
from spaces.services import (
    SpacePermissionService,
    audit_space_action,
    get_space_policy,
)
from spaces.views.memberships import _space_for_member


def _serialize_space(space, user):
    serializer = SpaceSerializer(space)
    data = dict(serializer.data)
    membership = SpacePermissionService.membership(user, space)
    data["role"] = membership.role if membership else None
    data["is_personal_owner"] = space.personal_owner_id == user.id
    data["is_global_admin"] = bool(user.is_staff)
    data["admin_takeover_active"] = bool(
        user.is_staff
        and SpaceTakeover.objects.filter(
            space=space, admin=user, active=True
        ).exists()
    )
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


class OwnerlessSpaceListAPIView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        spaces = Space.objects.filter(kind=Space.Kind.TEAM, owner__isnull=True)
        return Response({"data": SpaceSerializer(spaces, many=True).data})

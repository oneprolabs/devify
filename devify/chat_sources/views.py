from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from chat_sources.adapters import capabilities_for
from chat_sources.models import Source, SourceImport
from chat_sources.serializers import (
    SourceCreateSerializer,
    SourceImportSerializer,
    SourceSerializer,
    SourceUpdateSerializer,
)
from chat_sources.services import can_manage_source
from spaces.models import Space, SpaceMembership, SpaceTakeover
from spaces.services import SpacePermissionService, audit_space_action


def authorized_space(user, space_id, *, write=False):
    space = get_object_or_404(Space, pk=space_id)
    allowed = (
        SpacePermissionService.can_upload(user, space)
        if write
        else SpacePermissionService.can_read(user, space)
    )
    if not allowed:
        return None, None
    takeover = None
    if getattr(user, "is_staff", False):
        takeover = SpaceTakeover.objects.filter(
            space=space, admin=user, active=True
        ).first()
    return space, takeover


def _source_manager_response(user, source):
    return can_manage_source(user, source)


class SpaceSourceListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, space_id):
        space, takeover = authorized_space(request.user, space_id)
        if space is None:
            return Response({"detail": "Space not found."}, status=404)
        sources = Source.objects.filter(space=space).order_by(
            "display_name", "id"
        )
        imports = SourceImport.objects.filter(space=space).order_by(
            "-created_at", "-id"
        )[:100]
        data = {
            "sources": SourceSerializer(sources, many=True).data,
            "imports": SourceImportSerializer(imports, many=True).data,
        }
        if takeover:
            audit_space_action(
                actor=request.user,
                space=space,
                action="chat.source_list_viewed",
                resource_type="source",
                metadata={"takeover_id": takeover.pk},
            )
        return Response({"data": data})

    @transaction.atomic
    def post(self, request, space_id):
        space, takeover = authorized_space(request.user, space_id, write=True)
        if space is None:
            return Response({"detail": "Space not found."}, status=404)
        serializer = SourceCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if not can_manage_source_for_space(request.user, space):
            return Response(
                {"detail": "Source manager permission required."}, status=403
            )
        values = serializer.validated_data
        source = Source(
            space=space,
            created_by=request.user,
            updated_by=request.user,
            capabilities=capabilities_for(
                values["channel_type"], values["provider"]
            ),
            **values,
        )
        try:
            source.save()
        except IntegrityError:
            return Response(
                {"detail": "This source account is already bound."},
                status=409,
            )
        audit_space_action(
            actor=request.user,
            space=space,
            action="chat.source_created",
            resource_type="source",
            resource_id=source.pk,
            metadata={"takeover_id": takeover.pk if takeover else None},
        )
        return Response({"data": SourceSerializer(source).data}, status=201)


def can_manage_source_for_space(user, space):
    if getattr(user, "is_staff", False):
        return SpacePermissionService.has_active_takeover(user, space)
    membership = SpacePermissionService.membership(user, space)
    return bool(
        membership
        and membership.status == SpaceMembership.Status.ACTIVE
        and SpacePermissionService.can_manage(membership)
    )


class SourceDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, source_id):
        source = get_object_or_404(
            Source.objects.select_related("space"), pk=source_id
        )
        space, takeover = authorized_space(request.user, source.space_id)
        if space is None:
            return Response({"detail": "Source not found."}, status=404)
        if takeover:
            audit_space_action(
                actor=request.user,
                space=space,
                action="chat.source_viewed",
                resource_type="source",
                resource_id=source.pk,
                metadata={"takeover_id": takeover.pk},
            )
        return Response({"data": SourceSerializer(source).data})

    @transaction.atomic
    def patch(self, request, source_id):
        source = get_object_or_404(
            Source.objects.select_related("space"), pk=source_id
        )
        space, takeover = authorized_space(
            request.user, source.space_id, write=True
        )
        if space is None:
            return Response({"detail": "Source not found."}, status=404)
        if not _source_manager_response(request.user, source):
            return Response(
                {"detail": "Source manager permission required."}, status=403
            )
        serializer = SourceUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        for field, value in serializer.validated_data.items():
            setattr(source, field, value)
        source.updated_by = request.user
        source.save()
        audit_space_action(
            actor=request.user,
            space=space,
            action="chat.source_updated",
            resource_type="source",
            resource_id=source.pk,
            metadata={"takeover_id": takeover.pk if takeover else None},
        )
        return Response({"data": SourceSerializer(source).data})

    @transaction.atomic
    def delete(self, request, source_id):
        source = get_object_or_404(
            Source.objects.select_related("space"), pk=source_id
        )
        space, takeover = authorized_space(
            request.user, source.space_id, write=True
        )
        if space is None:
            return Response({"detail": "Source not found."}, status=404)
        if not _source_manager_response(request.user, source):
            return Response(
                {"detail": "Source manager permission required."}, status=403
            )
        source.status = Source.Status.DISABLED
        source.updated_by = request.user
        source.save(update_fields=("status", "updated_by", "updated_at"))
        audit_space_action(
            actor=request.user,
            space=space,
            action="chat.source_disabled",
            resource_type="source",
            resource_id=source.pk,
            metadata={"takeover_id": takeover.pk if takeover else None},
        )
        return Response(status=204)

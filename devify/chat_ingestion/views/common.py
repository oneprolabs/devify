"""Shared upload authorization and HTTP response helpers."""

import logging

from django.shortcuts import get_object_or_404
from rest_framework.response import Response

from chat_ingestion.models import UploadBatch
from chat_ingestion.serializers import UploadBatchSerializer
from spaces.models import Space, SpaceTakeover
from spaces.services import SpacePermissionService

logger = logging.getLogger("chat_ingestion.views")


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
    membership = SpacePermissionService.membership(user, batch.space)
    if SpacePermissionService.can_write(membership) and (
        user.pk == batch.uploaded_by_id
        or SpacePermissionService.can_manage(membership)
    ):
        return True
    return bool(
        getattr(user, "is_staff", False)
        and SpacePermissionService.has_active_takeover(user, batch.space)
    )


def _read_only_response():
    return Response({"detail": "Archived spaces are read-only."}, status=409)


def _batch_response(batch, status_code=200):
    return Response(
        {"data": UploadBatchSerializer(batch).data}, status=status_code
    )

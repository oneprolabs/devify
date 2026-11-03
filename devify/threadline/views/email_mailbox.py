"""API for the mailboxes a user has connected."""

import logging

from django.conf import settings as django_settings
from django.contrib.auth.models import User
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from expense.services.config_service import (
    get_user_config,
    get_user_config_for_update,
    set_user_enabled,
)
from threadline.models import EmailMailbox
from threadline.serializers.email_mailbox import EmailMailboxSerializer
from threadline.utils.email.config import EmailConfigManager

logger = logging.getLogger(__name__)


def _response(data, message="ok", code=200, status_code=status.HTTP_200_OK):
    return Response(
        {"code": code, "message": message, "data": data}, status=status_code
    )


def _enable_expense_for_invoice_mailbox(user: User) -> None:
    """Keep invoice-only mailboxes usable as soon as they are saved."""
    set_user_enabled(get_user_config(user), True)


class EmailMailboxListAPIView(APIView):
    """List the user's mailboxes, or connect another one."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = EmailMailbox.objects.filter(user=request.user)
        return _response(
            {
                "mailboxes": EmailMailboxSerializer(
                    queryset, many=True, context={"request": request}
                ).data,
                "max_mailboxes": getattr(
                    django_settings, "MAX_USER_MAILBOXES", 5
                ),
            }
        )

    def post(self, request):
        serializer = EmailMailboxSerializer(
            data=request.data or {}, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            if serializer.validated_data.get("invoice_only", False):
                _enable_expense_for_invoice_mailbox(request.user)
            mailbox = serializer.save()
        return _response(
            EmailMailboxSerializer(
                mailbox, context={"request": request}
            ).data,
            message="created",
            code=201,
            status_code=status.HTTP_201_CREATED,
        )


class EmailMailboxDetailAPIView(APIView):
    """Edit or disconnect one mailbox."""

    permission_classes = [IsAuthenticated]

    def _get_object(self, request, uuid, *, for_update=False):
        queryset = EmailMailbox.objects
        if for_update:
            queryset = queryset.select_for_update()
        return get_object_or_404(queryset, uuid=uuid, user=request.user)

    def get(self, request, uuid):
        mailbox = self._get_object(request, uuid)
        return _response(
            EmailMailboxSerializer(
                mailbox, context={"request": request}
            ).data
        )

    def patch(self, request, uuid):
        with transaction.atomic():
            expense_config = get_user_config_for_update(request.user)
            mailbox = self._get_object(request, uuid, for_update=True)
            serializer = EmailMailboxSerializer(
                mailbox,
                data=request.data,
                partial=True,
                context={"request": request},
            )
            serializer.is_valid(raise_exception=True)
            if serializer.validated_data.get(
                "invoice_only", mailbox.invoice_only
            ):
                set_user_enabled(expense_config, True)
            mailbox = serializer.save()
        return _response(
            EmailMailboxSerializer(
                mailbox, context={"request": request}
            ).data
        )

    def delete(self, request, uuid):
        mailbox = self._get_object(request, uuid)
        mailbox.delete()
        return _response(None, message="deleted")


class EmailMailboxTestAPIView(APIView):
    """
    Check that a mailbox actually connects.

    Accepts either a stored mailbox or a draft that has not been saved
    yet, so credentials can be checked before they are committed.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, uuid=None):
        # The validator takes the whole email config and reads `imap_config`
        # out of it, so the settings have to stay nested here.
        if uuid:
            mailbox = get_object_or_404(
                EmailMailbox, uuid=uuid, user=request.user
            )
            config = mailbox.to_email_config()
        else:
            payload = request.data or {}
            port = payload.get("imap_port") or 993
            password = payload.get("password") or ""
            if not password and payload.get("uuid"):
                # Editing a mailbox leaves the password field empty to keep
                # the stored one; the test has to use it too.
                stored = EmailMailbox.objects.filter(
                    uuid=payload["uuid"], user=request.user
                ).first()
                password = stored.password if stored else ""
            config = {
                "imap_config": {
                    "imap_host": (payload.get("imap_host") or "").strip(),
                    "imap_port": port,
                    "imap_ssl_port": port,
                    "use_ssl": payload.get("use_ssl", True),
                    "username": (payload.get("username") or "").strip(),
                    "password": password,
                    "folder": payload.get("folder") or "INBOX",
                },
                "filter_config": {},
            }

        is_valid, error_message = EmailConfigManager.validate_imap_connection(
            config,
            user_context=f"{request.user.username} (ID: {request.user.id})",
        )
        if not is_valid:
            return _response(
                {"success": False},
                message=error_message or "IMAP validation failed",
                code=400,
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        return _response({"success": True}, message="connected")

class SpaceEmailSourceListAPIView(APIView):
    """Space-scoped mailbox configuration; legacy user mailbox routes remain intact."""

    permission_classes = [IsAuthenticated]

    def _space(self, request, space_id, *, write=False):
        from spaces.models import Space
        from spaces.services import SpacePermissionService

        space = get_object_or_404(Space, pk=space_id)
        allowed = SpacePermissionService.can_upload(request.user, space) if write else SpacePermissionService.can_read(request.user, space)
        if not allowed:
            return None
        return space

    def get(self, request, space_id):
        space = self._space(request, space_id)
        if space is None:
            return _response({"detail": "Space not found."}, code=404, status_code=404)
        mailboxes = EmailMailbox.objects.filter(space=space).order_by("created_at")
        return _response({"mailboxes": EmailMailboxSerializer(mailboxes, many=True, context={"request": request}).data})

    def post(self, request, space_id):
        space = self._space(request, space_id, write=True)
        if space is None:
            return _response({"detail": "Space not found."}, code=404, status_code=404)
        from spaces.services import SpacePermissionService
        membership = SpacePermissionService.membership(request.user, space)
        if not (request.user.is_staff and SpacePermissionService.has_active_takeover(request.user, space) or SpacePermissionService.can_manage(membership)):
            return _response({"detail": "Space email source permission required."}, code=403, status_code=403)
        serializer = EmailMailboxSerializer(data=request.data or {}, context={"request": request})
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            mailbox = serializer.save(space=space)
        return _response(EmailMailboxSerializer(mailbox, context={"request": request}).data, message="created", code=201, status_code=201)

class SpaceEmailSourceDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_space(self, request, space_id, *, write=False):
        from spaces.models import Space
        from spaces.services import SpacePermissionService
        space = get_object_or_404(Space, pk=space_id)
        if not (SpacePermissionService.can_upload(request.user, space) if write else SpacePermissionService.can_read(request.user, space)):
            return None
        return space

    def _get_mailbox(self, request, space_id, mailbox_uuid, *, write=False):
        space = self._get_space(request, space_id, write=write)
        if space is None:
            return None, None
        mailbox = get_object_or_404(EmailMailbox, space=space, uuid=mailbox_uuid)
        return space, mailbox

    def patch(self, request, space_id, mailbox_uuid):
        space, mailbox = self._get_mailbox(request, space_id, mailbox_uuid, write=True)
        if mailbox is None:
            return _response({"detail": "Email source not found."}, code=404, status_code=404)
        from spaces.services import SpacePermissionService
        membership = SpacePermissionService.membership(request.user, space)
        if not (request.user.is_staff and SpacePermissionService.has_active_takeover(request.user, space) or SpacePermissionService.can_manage(membership)):
            return _response({"detail": "Space email source permission required."}, code=403, status_code=403)
        serializer = EmailMailboxSerializer(mailbox, data=request.data, partial=True, context={"request": request})
        serializer.is_valid(raise_exception=True)
        mailbox = serializer.save()
        return _response(EmailMailboxSerializer(mailbox, context={"request": request}).data)

    def delete(self, request, space_id, mailbox_uuid):
        space, mailbox = self._get_mailbox(request, space_id, mailbox_uuid, write=True)
        if mailbox is None:
            return _response({"detail": "Email source not found."}, code=404, status_code=404)
        from spaces.services import SpacePermissionService
        membership = SpacePermissionService.membership(request.user, space)
        if not (request.user.is_staff and SpacePermissionService.has_active_takeover(request.user, space) or SpacePermissionService.can_manage(membership)):
            return _response({"detail": "Space email source permission required."}, code=403, status_code=403)
        mailbox.enabled = False
        mailbox.save(update_fields=("enabled", "updated_at"))
        return _response(None, message="disabled")

class SpaceEmailSourceTestAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, space_id, mailbox_uuid=None):
        from spaces.models import Space
        from spaces.services import SpacePermissionService
        space = get_object_or_404(Space, pk=space_id)
        membership = SpacePermissionService.membership(request.user, space)
        allowed = SpacePermissionService.can_manage(membership) or (request.user.is_staff and SpacePermissionService.has_active_takeover(request.user, space))
        if not allowed:
            return _response({"detail": "Space email source permission required."}, code=403, status_code=403)
        if mailbox_uuid:
            mailbox = get_object_or_404(EmailMailbox, space=space, uuid=mailbox_uuid)
            config = mailbox.to_email_config()
        else:
            payload = request.data or {}
            config = {"imap_config": {"imap_host": (payload.get("imap_host") or "").strip(), "imap_port": payload.get("imap_port") or 993, "imap_ssl_port": payload.get("imap_port") or 993, "use_ssl": payload.get("use_ssl", True), "username": (payload.get("username") or "").strip(), "password": payload.get("password") or "", "folder": payload.get("folder") or "INBOX"}, "filter_config": {}}
        is_valid, error_message = EmailConfigManager.validate_imap_connection(config, user_context=f"space:{space.pk} user:{request.user.pk}")
        if not is_valid:
            return _response({"success": False}, message=error_message or "IMAP validation failed", code=400, status_code=400)
        return _response({"success": True}, message="connected")


class SpaceEmailSourceSyncAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, space_id, mailbox_uuid):
        from spaces.models import Space
        from spaces.services import SpacePermissionService
        space = get_object_or_404(Space, pk=space_id)
        membership = SpacePermissionService.membership(request.user, space)
        can_manage = SpacePermissionService.can_manage(membership) or (request.user.is_staff and SpacePermissionService.has_active_takeover(request.user, space))
        if not can_manage:
            return _response({"detail": "Space email source permission required."}, code=403, status_code=403)
        mailbox = get_object_or_404(EmailMailbox, space=space, uuid=mailbox_uuid)
        if not mailbox.enabled:
            return _response({"detail": "Email source is disabled."}, code=409, status_code=409)
        return _response({"source_id": str(mailbox.uuid), "status": "not_started", "reason": "邮箱抓取调度仍由现有账号级调度器执行，空间级启动任务尚未接入。"}, message="not_started")

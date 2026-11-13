"""API for the mailboxes a user has connected."""

import logging

from django.conf import settings as django_settings
from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Q
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
from threadline.models import (
    EmailMailbox,
    EmailMailboxShare,
    compute_mailbox_source_key,
)
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


def _personal_mailboxes(user):
    """Mailboxes owned by the user's personal space.

    Team-owned sources are managed through the space source API. The legacy
    settings page must not edit or delete them, even though the creator is
    still the technical credential holder.
    """
    return EmailMailbox.objects.filter(user=user).filter(
        Q(space__isnull=True)
        | Q(space__kind="personal", space__personal_owner=user)
    )


class EmailMailboxListAPIView(APIView):
    """List the user's mailboxes, or connect another one."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = _personal_mailboxes(request.user)
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
            EmailMailboxSerializer(mailbox, context={"request": request}).data,
            message="created",
            code=201,
            status_code=status.HTTP_201_CREATED,
        )


class EmailMailboxDetailAPIView(APIView):
    """Edit or disconnect one mailbox."""

    permission_classes = [IsAuthenticated]

    def _get_object(self, request, uuid, *, for_update=False):
        queryset = _personal_mailboxes(request.user)
        if for_update:
            queryset = queryset.select_for_update()
        return get_object_or_404(queryset, uuid=uuid)

    def get(self, request, uuid):
        mailbox = self._get_object(request, uuid)
        return _response(
            EmailMailboxSerializer(mailbox, context={"request": request}).data
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
            EmailMailboxSerializer(mailbox, context={"request": request}).data
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
                _personal_mailboxes(request.user), uuid=uuid
            )
            config = mailbox.to_email_config()
        else:
            payload = request.data or {}
            port = payload.get("imap_port") or 993
            password = payload.get("password") or ""
            if not password and payload.get("uuid"):
                # Editing a mailbox leaves the password field empty to keep
                # the stored one; the test has to use it too.
                stored = _personal_mailboxes(request.user).filter(
                    uuid=payload["uuid"]
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
    """Space-scoped mailbox configuration.

    Legacy user mailbox routes remain intact.
    """

    permission_classes = [IsAuthenticated]

    def _space(self, request, space_id, *, write=False):
        from spaces.models import Space
        from spaces.services import SpacePermissionService

        space = get_object_or_404(Space, pk=space_id)
        allowed = (
            SpacePermissionService.can_upload(request.user, space)
            if write
            else SpacePermissionService.can_read(request.user, space)
        )
        if not allowed:
            return None
        return space

    def get(self, request, space_id):
        space = self._space(request, space_id)
        if space is None:
            return _response(
                {"detail": "Space not found."}, code=404, status_code=404
            )
        mailboxes = EmailMailbox.objects.filter(space=space).order_by(
            "created_at"
        )
        return _response(
            {
                "mailboxes": EmailMailboxSerializer(
                    mailboxes, many=True, context={"request": request}
                ).data
            }
        )

    def post(self, request, space_id):
        space = self._space(request, space_id, write=True)
        if space is None:
            return _response(
                {"detail": "Space not found."}, code=404, status_code=404
            )
        from spaces.services import SpacePermissionService

        membership = SpacePermissionService.membership(request.user, space)
        if not (
            request.user.is_staff
            and SpacePermissionService.has_active_takeover(request.user, space)
            or SpacePermissionService.can_manage(membership)
        ):
            return _response(
                {"detail": "Space email source permission required."},
                code=403,
                status_code=403,
            )
        payload = request.data or {}
        try:
            imap_port = int(payload.get("imap_port") or 993)
        except (TypeError, ValueError):
            imap_port = 993
        use_ssl = payload.get("use_ssl", True)
        if isinstance(use_ssl, str):
            use_ssl = use_ssl.strip().lower() in {"1", "true", "yes", "on"}
        source_key = compute_mailbox_source_key(
            payload.get("imap_host"),
            imap_port,
            payload.get("username"),
            payload.get("folder") or "INBOX",
            bool(use_ssl),
        )
        existing = EmailMailbox.objects.filter(source_key=source_key).first()
        if existing is not None:
            return _response(
                {
                    "detail": (
                        "This mailbox is already connected. Ask its owner "
                        "to share it with this space."
                    ),
                    "mailbox_uuid": str(existing.uuid),
                    "existing_space_id": existing.space_id,
                },
                code=409,
                status_code=409,
            )

        serializer = EmailMailboxSerializer(
            data=request.data or {}, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            mailbox = serializer.save(space=space)
        return _response(
            EmailMailboxSerializer(mailbox, context={"request": request}).data,
            message="created",
            code=201,
            status_code=201,
        )


class SpaceEmailSourceDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_space(self, request, space_id, *, write=False):
        from spaces.models import Space
        from spaces.services import SpacePermissionService

        space = get_object_or_404(Space, pk=space_id)
        if not (
            SpacePermissionService.can_upload(request.user, space)
            if write
            else SpacePermissionService.can_read(request.user, space)
        ):
            return None
        return space

    def _get_mailbox(self, request, space_id, mailbox_uuid, *, write=False):
        space = self._get_space(request, space_id, write=write)
        if space is None:
            return None, None
        mailbox = get_object_or_404(
            EmailMailbox, space=space, uuid=mailbox_uuid
        )
        return space, mailbox

    def patch(self, request, space_id, mailbox_uuid):
        space, mailbox = self._get_mailbox(
            request, space_id, mailbox_uuid, write=True
        )
        if mailbox is None:
            return _response(
                {"detail": "Email source not found."},
                code=404,
                status_code=404,
            )
        from spaces.services import SpacePermissionService

        membership = SpacePermissionService.membership(request.user, space)
        if not (
            request.user.is_staff
            and SpacePermissionService.has_active_takeover(request.user, space)
            or SpacePermissionService.can_manage(membership)
        ):
            return _response(
                {"detail": "Space email source permission required."},
                code=403,
                status_code=403,
            )
        serializer = EmailMailboxSerializer(
            mailbox,
            data=request.data,
            partial=True,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        mailbox = serializer.save()
        return _response(
            EmailMailboxSerializer(mailbox, context={"request": request}).data
        )

    def delete(self, request, space_id, mailbox_uuid):
        space, mailbox = self._get_mailbox(
            request, space_id, mailbox_uuid, write=True
        )
        if mailbox is None:
            return _response(
                {"detail": "Email source not found."},
                code=404,
                status_code=404,
            )
        from spaces.services import SpacePermissionService

        membership = SpacePermissionService.membership(request.user, space)
        if not (
            request.user.is_staff
            and SpacePermissionService.has_active_takeover(request.user, space)
            or SpacePermissionService.can_manage(membership)
        ):
            return _response(
                {"detail": "Space email source permission required."},
                code=403,
                status_code=403,
            )
        mailbox.enabled = False
        mailbox.save(update_fields=("enabled", "updated_at"))
        return _response(None, message="disabled")


class SpaceEmailSourceShareAPIView(APIView):
    """Share one source to another space, or revoke that visibility."""

    permission_classes = [IsAuthenticated]

    def _owner(self, request, space_id, mailbox_uuid):
        from spaces.models import Space
        from spaces.services import SpacePermissionService

        space = get_object_or_404(Space, pk=space_id)
        membership = SpacePermissionService.membership(request.user, space)
        allowed = SpacePermissionService.can_manage(membership) or (
            request.user.is_staff
            and SpacePermissionService.has_active_takeover(
                request.user, space
            )
        )
        if not allowed:
            return None, None
        mailbox = get_object_or_404(
            EmailMailbox, space=space, uuid=mailbox_uuid
        )
        return space, mailbox

    def post(self, request, space_id, mailbox_uuid):
        from spaces.models import Space
        from spaces.services import (
            SpacePermissionService,
            audit_space_action,
        )
        space, mailbox = self._owner(request, space_id, mailbox_uuid)
        if mailbox is None:
            return _response(
                {"detail": "Space email source permission required."},
                code=403,
                status_code=403,
            )
        target_id = request.data.get("space_id")
        if not target_id:
            return _response(
                {"detail": "space_id is required."},
                code=400,
                status_code=400,
            )
        target = get_object_or_404(Space, pk=target_id)
        target_membership = SpacePermissionService.membership(
            request.user, target
        )
        can_manage_target = (
            SpacePermissionService.can_manage(target_membership)
            or (
                target.kind == Space.Kind.PERSONAL
                and target.personal_owner_id == request.user.id
            )
            or (
                request.user.is_staff
                and SpacePermissionService.has_active_takeover(
                    request.user, target
                )
            )
        )
        if not can_manage_target:
            return _response(
                {"detail": "Target space permission required."},
                code=403,
                status_code=403,
            )
        permission = request.data.get(
            "permission", EmailMailboxShare.Permission.READ
        )
        if permission not in EmailMailboxShare.Permission.values:
            return _response(
                {"detail": "Invalid permission."},
                code=400,
                status_code=400,
            )
        share, created = EmailMailboxShare.objects.get_or_create(
            mailbox=mailbox,
            space=target,
            defaults={
                "permission": permission,
                "created_by": request.user,
            },
        )
        if not created and share.permission != permission:
            share.permission = permission
            share.save(update_fields=("permission",))
        audit_space_action(
            actor=request.user,
            space=space,
            action="email.source_shared",
            resource_type="email_mailbox",
            resource_id=mailbox.pk,
            metadata={
                "target_space_id": target.pk,
                "permission": permission,
            },
        )
        return _response(
            {
                "mailbox_uuid": str(mailbox.uuid),
                "space_id": target.pk,
                "permission": permission,
            },
            message="shared",
            code=201 if created else 200,
            status_code=201 if created else 200,
        )

    def delete(self, request, space_id, mailbox_uuid):
        from spaces.services import audit_space_action
        space, mailbox = self._owner(request, space_id, mailbox_uuid)
        if mailbox is None:
            return _response(
                {"detail": "Space email source permission required."},
                code=403,
                status_code=403,
            )
        target_id = request.query_params.get("space_id")
        if not target_id:
            return _response(
                {"detail": "space_id is required."},
                code=400,
                status_code=400,
            )
        if int(target_id) == mailbox.space_id:
            return _response(
                {"detail": "The owner space share cannot be removed."},
                code=409,
                status_code=409,
            )
        EmailMailboxShare.objects.filter(
            mailbox=mailbox, space_id=target_id
        ).delete()
        audit_space_action(
            actor=request.user,
            space=space,
            action="email.source_unshared",
            resource_type="email_mailbox",
            resource_id=mailbox.pk,
            metadata={"target_space_id": int(target_id)},
        )
        return _response(None, message="unshared")


class SpaceEmailSourceTransferAPIView(APIView):
    """Move a source's ownership to another space."""

    permission_classes = [IsAuthenticated]

    def post(self, request, space_id, mailbox_uuid):
        from spaces.models import Space
        from spaces.services import (
            SpacePermissionService,
            audit_space_action,
        )
        space = get_object_or_404(Space, pk=space_id)
        membership = SpacePermissionService.membership(request.user, space)
        allowed = SpacePermissionService.can_manage(membership) or (
            request.user.is_staff
            and SpacePermissionService.has_active_takeover(
                request.user, space
            )
        )
        if not allowed:
            return _response(
                {"detail": "Space email source permission required."},
                code=403,
                status_code=403,
            )
        mailbox = get_object_or_404(
            EmailMailbox, space=space, uuid=mailbox_uuid
        )
        target_id = request.data.get("space_id")
        if not target_id:
            return _response(
                {"detail": "space_id is required."},
                code=400,
                status_code=400,
            )
        target = get_object_or_404(Space, pk=target_id)
        if target.pk == space.pk:
            return _response(
                {"detail": "Already owned by this space."},
                code=409,
                status_code=409,
            )
        target_membership = SpacePermissionService.membership(
            request.user, target
        )
        can_manage_target = (
            SpacePermissionService.can_manage(target_membership)
            or (
                target.kind == Space.Kind.PERSONAL
                and target.personal_owner_id == request.user.id
            )
            or (
                request.user.is_staff
                and SpacePermissionService.has_active_takeover(
                    request.user, target
                )
            )
        )
        if not can_manage_target:
            return _response(
                {"detail": "Target space permission required."},
                code=403,
                status_code=403,
            )
        with transaction.atomic():
            old_share, _ = EmailMailboxShare.objects.get_or_create(
                mailbox=mailbox,
                space=space,
                defaults={
                    "permission": EmailMailboxShare.Permission.READ,
                    "created_by": request.user,
                },
            )
            old_share.permission = EmailMailboxShare.Permission.READ
            old_share.save(update_fields=("permission",))
            target_share, _ = EmailMailboxShare.objects.get_or_create(
                mailbox=mailbox,
                space=target,
                defaults={
                    "permission": EmailMailboxShare.Permission.MANAGE,
                    "created_by": request.user,
                },
            )
            target_share.permission = EmailMailboxShare.Permission.MANAGE
            target_share.save(update_fields=("permission",))
            mailbox.space = target
            mailbox.save(update_fields=("space", "updated_at"))
            audit_space_action(
                actor=request.user,
                space=space,
                action="email.source_transferred",
                resource_type="email_mailbox",
                resource_id=mailbox.pk,
                metadata={"target_space_id": target.pk},
            )
        return _response(
            {"mailbox_uuid": str(mailbox.uuid), "space_id": target.pk},
            message="transferred",
        )


class SpaceEmailSourceTestAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, space_id, mailbox_uuid=None):
        from spaces.models import Space
        from spaces.services import SpacePermissionService

        space = get_object_or_404(Space, pk=space_id)
        membership = SpacePermissionService.membership(request.user, space)
        allowed = SpacePermissionService.can_manage(membership) or (
            request.user.is_staff
            and SpacePermissionService.has_active_takeover(request.user, space)
        )
        if not allowed:
            return _response(
                {"detail": "Space email source permission required."},
                code=403,
                status_code=403,
            )
        if mailbox_uuid:
            mailbox = get_object_or_404(
                EmailMailbox, space=space, uuid=mailbox_uuid
            )
            config = mailbox.to_email_config()
        else:
            payload = request.data or {}
            config = {
                "imap_config": {
                    "imap_host": (payload.get("imap_host") or "").strip(),
                    "imap_port": payload.get("imap_port") or 993,
                    "imap_ssl_port": payload.get("imap_port") or 993,
                    "use_ssl": payload.get("use_ssl", True),
                    "username": (payload.get("username") or "").strip(),
                    "password": payload.get("password") or "",
                    "folder": payload.get("folder") or "INBOX",
                },
                "filter_config": {},
            }
        is_valid, error_message = EmailConfigManager.validate_imap_connection(
            config, user_context=f"space:{space.pk} user:{request.user.pk}"
        )
        if not is_valid:
            return _response(
                {"success": False},
                message=error_message or "IMAP validation failed",
                code=400,
                status_code=400,
            )
        return _response({"success": True}, message="connected")


class SpaceEmailSourceSyncAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, space_id, mailbox_uuid):
        from spaces.models import Space
        from spaces.services import SpacePermissionService

        space = get_object_or_404(Space, pk=space_id)
        membership = SpacePermissionService.membership(request.user, space)
        can_manage = SpacePermissionService.can_manage(membership) or (
            request.user.is_staff
            and SpacePermissionService.has_active_takeover(request.user, space)
        )
        if not can_manage:
            return _response(
                {"detail": "Space email source permission required."},
                code=403,
                status_code=403,
            )
        mailbox = get_object_or_404(
            EmailMailbox, space=space, uuid=mailbox_uuid
        )
        if not mailbox.enabled:
            return _response(
                {"detail": "Email source is disabled."},
                code=409,
                status_code=409,
            )
        return _response(
            {
                "source_id": str(mailbox.uuid),
                "status": "account_scheduler",
                "reason": (
                    "该来源由账号级 IMAP 调度器统一抓取，"
                    "无需手动启动空间任务。"
                ),
            },
            message="account_scheduler",
        )

"""API for the mailboxes a user has connected."""

import logging

from django.conf import settings as django_settings
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from threadline.models import EmailMailbox
from threadline.serializers.email_mailbox import EmailMailboxSerializer
from threadline.utils.email.config import EmailConfigManager

logger = logging.getLogger(__name__)


def _response(data, message="ok", code=200, status_code=status.HTTP_200_OK):
    return Response(
        {"code": code, "message": message, "data": data}, status=status_code
    )


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

    def _get_object(self, request, uuid):
        return get_object_or_404(EmailMailbox, uuid=uuid, user=request.user)

    def get(self, request, uuid):
        mailbox = self._get_object(request, uuid)
        return _response(
            EmailMailboxSerializer(
                mailbox, context={"request": request}
            ).data
        )

    def patch(self, request, uuid):
        mailbox = self._get_object(request, uuid)
        serializer = EmailMailboxSerializer(
            mailbox,
            data=request.data,
            partial=True,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
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
        if uuid:
            mailbox = get_object_or_404(
                EmailMailbox, uuid=uuid, user=request.user
            )
            config = mailbox.to_email_config()["imap_config"]
        else:
            payload = request.data or {}
            config = {
                "imap_host": payload.get("imap_host", ""),
                "imap_port": payload.get("imap_port", 993),
                "imap_ssl_port": payload.get("imap_port", 993),
                "use_ssl": payload.get("use_ssl", True),
                "username": payload.get("username", ""),
                "password": payload.get("password", ""),
                "folder": payload.get("folder", "INBOX"),
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

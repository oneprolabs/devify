"""HTTP endpoints for desktop settings and backup lookups."""

from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework.parsers import JSONParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from spaces.models import Space
from spaces.serializers.desktop_backup import SaveSerializer
from spaces.services import SpacePermissionService
from spaces.services.desktop_backup import (
    AmbiguousConversation,
    DeviceAuthorizationRequired,
    IdempotencyKeyReused,
    find_conversation,
    find_message_keys,
    save_backup_config,
)


class DesktopBackupConfigAPIView(APIView):
    permission_classes = [IsAuthenticated]
    # Conversation IDs are opaque keys; never camel-case them.
    parser_classes = [JSONParser]

    @transaction.atomic
    def put(self, request, space_id):
        if len(request.body) > 2 * 1024 * 1024:
            return Response(
                {"detail": "Configuration exceeds 2 MiB."}, status=413
            )
        space = get_object_or_404(Space, pk=space_id)
        if not SpacePermissionService.can_upload(request.user, space):
            return Response({"detail": "Space not found."}, status=404)
        serializer = SaveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        try:
            result = save_backup_config(request.user, space, values)
        except DeviceAuthorizationRequired:
            return Response(
                {"detail": "Device authorization is required."}, status=403
            )
        except IdempotencyKeyReused:
            return Response({"detail": "IDEMPOTENCY_KEY_REUSED"}, status=409)
        return Response({"data": result})


class DesktopMessageKeysAPIView(APIView):
    """Only resolve keys in the bounded batch; never download chat history."""

    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]

    def post(self, request, space_id):
        if len(request.body) > 256 * 1024:
            return Response({"detail": "Key query is too large."}, status=413)
        space = get_object_or_404(Space, pk=space_id)
        if not SpacePermissionService.can_upload(request.user, space):
            return Response({"detail": "Space not found."}, status=404)
        data = request.data
        if not isinstance(data, dict) or set(data) != {
            "source_account_id",
            "queries",
        }:
            return Response({"detail": "Invalid key query."}, status=400)
        account = data["source_account_id"]
        queries = data["queries"]
        if (
            not isinstance(account, str)
            or not account
            or len(account) > 255
            or not isinstance(queries, list)
            or len(queries) > 8
        ):
            return Response({"detail": "Invalid key scope."}, status=400)
        result = []
        total = 0
        for query in queries:
            if not isinstance(query, dict) or set(query) != {
                "username",
                "keys",
            }:
                return Response({"detail": "Invalid key query."}, status=400)
            name, keys = query["username"], query["keys"]
            if (
                not isinstance(name, str)
                or not isinstance(keys, list)
                or any(not isinstance(k, str) or len(k) > 255 for k in keys)
            ):
                return Response(
                    {"detail": "Invalid message keys."}, status=400
                )
            total += len(keys)
            if total > 1000:
                return Response(
                    {"detail": "Too many message keys."}, status=400
                )
            try:
                found = find_message_keys(space, account, name, keys)
            except AmbiguousConversation:
                return Response(
                    {"detail": "Ambiguous conversation."}, status=409
                )
            result.append({"username": name, "keys": found})
        return Response({"data": {"list": result}})


class DesktopConversationLookupAPIView(APIView):
    """Look up a backup when the opened local records are missing."""

    permission_classes = [IsAuthenticated]

    def get(self, request, space_id):
        space = get_object_or_404(Space, pk=space_id)
        if not SpacePermissionService.can_read(request.user, space):
            return Response({"detail": "Space not found."}, status=404)
        platform = request.query_params.get("platform")
        account = request.query_params.get("source_account_id", "")
        name = request.query_params.get("source_conversation_id", "")
        if (
            platform not in {"wechat", "whatsapp"}
            or not account
            or not name
            or len(account) > 255
            or len(name) > 255
        ):
            return Response({"detail": "Invalid source scope."}, status=400)
        try:
            row = find_conversation(space, platform, account, name)
        except AmbiguousConversation:
            return Response({"detail": "Ambiguous conversation."}, status=409)
        return Response(
            {
                "data": {
                    "conversation": (
                        {"id": row.pk, "title": row.title} if row else None
                    )
                }
            }
        )

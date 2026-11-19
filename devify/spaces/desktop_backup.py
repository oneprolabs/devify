"""Single-direction desktop backup settings; no merge or remote-version protocol."""

import hashlib
import json

from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import JSONParser
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import DesktopDevice
from spaces.models import DesktopBackupConfig, DesktopConfigReceipt, Space
from spaces.services import SpacePermissionService


class StrictSerializer(serializers.Serializer):
    def to_internal_value(self, data):
        if not isinstance(data, dict) or set(data) - set(self.fields):
            raise serializers.ValidationError(
                "Unknown or invalid configuration fields."
            )
        return super().to_internal_value(data)


class RangeSerializer(StrictSerializer):
    since = serializers.IntegerField(allow_null=True)
    until = serializers.IntegerField(allow_null=True)

    def validate(self, data):
        if (
            data["since"] is not None
            and data["until"] is not None
            and data["since"] >= data["until"]
        ):
            raise serializers.ValidationError("Invalid history range.")
        return data


class BackupSerializer(StrictSerializer):
    mode = serializers.ChoiceField(choices=("interval", "times", "manual"))
    times = serializers.ListField(
        child=serializers.RegexField(r"^([01][0-9]|2[0-3]):[0-5][0-9]$"), max_length=24
    )
    window_enabled = serializers.BooleanField()
    window_mode = serializers.ChoiceField(choices=("allow", "deny"))
    window_start = serializers.RegexField(r"^([01][0-9]|2[0-3]):[0-5][0-9]$")
    window_end = serializers.RegexField(r"^([01][0-9]|2[0-3]):[0-5][0-9]$")
    days = serializers.ListField(
        child=serializers.IntegerField(min_value=0, max_value=6), max_length=7
    )
    wifi_only = serializers.BooleanField()
    attachments = serializers.ChoiceField(choices=("text", "images", "all"))


class PayloadSerializer(StrictSerializer):
    setup_state = serializers.ChoiceField(choices=("draft", "completed"))
    enabled = serializers.BooleanField()
    usernames = serializers.ListField(
        child=serializers.CharField(max_length=255), max_length=1000
    )
    initial_ranges = serializers.DictField(child=RangeSerializer())
    sync_interval_seconds = serializers.IntegerField(min_value=60, max_value=3596400)
    backup = BackupSerializer()

    def validate(self, data):
        if set(data["initial_ranges"]) - set(data["usernames"]):
            raise serializers.ValidationError(
                "History ranges must belong to selected conversations."
            )
        return data


class TargetSerializer(StrictSerializer):
    platform = serializers.ChoiceField(choices=("wechat", "whatsapp"))
    source_account_id = serializers.CharField(max_length=255)


class SaveSerializer(StrictSerializer):
    schema_version = serializers.IntegerField(min_value=1, max_value=1)
    device_id = serializers.CharField(max_length=100)
    mutation_id = serializers.CharField(max_length=100)
    local_revision = serializers.IntegerField(min_value=0)
    target = TargetSerializer()
    payload = PayloadSerializer()


class DesktopBackupConfigAPIView(APIView):
    permission_classes = [IsAuthenticated]
    # Conversation identifiers are opaque map keys, never camel-case transformed.
    parser_classes = [JSONParser]

    @transaction.atomic
    def put(self, request, space_id):
        if len(request.body) > 2 * 1024 * 1024:
            return Response({"detail": "Configuration exceeds 2 MiB."}, status=413)
        space = get_object_or_404(Space, pk=space_id)
        if not SpacePermissionService.can_upload(request.user, space):
            return Response({"detail": "Space not found."}, status=404)
        serializer = SaveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        device = (
            DesktopDevice.objects.select_for_update()
            .filter(
                user=request.user,
                device_id=values["device_id"],
                status=DesktopDevice.Status.ACTIVE,
            )
            .first()
        )
        if device is None:
            return Response({"detail": "Device authorization is required."}, status=403)
        digest = hashlib.sha256(
            json.dumps(values, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        scope = dict(user=request.user, space=space, device_id=device.device_id)
        receipt = DesktopConfigReceipt.objects.filter(
            **scope, mutation_id=values["mutation_id"]
        ).first()
        if receipt:
            if receipt.digest != digest:
                return Response({"detail": "IDEMPOTENCY_KEY_REUSED"}, status=409)
            return Response({"data": receipt.result})
        target = (
            values["target"]["platform"] + ":" + values["target"]["source_account_id"]
        )
        config, _ = DesktopBackupConfig.objects.get_or_create(**scope, target=target)
        payload = values["payload"]
        if payload["setup_state"] == "completed":
            config.completed = payload
            config.draft = {}
        else:
            config.draft = payload
        config.save(update_fields=("completed", "draft", "updated_at"))
        result = {
            "mutation_id": values["mutation_id"],
            "local_revision": values["local_revision"],
            "target": values["target"],
            "saved": True,
        }
        DesktopConfigReceipt.objects.create(
            **scope, mutation_id=values["mutation_id"], digest=digest, result=result
        )
        return Response({"data": result})


class DesktopMessageKeysAPIView(APIView):
    """Only resolve keys in the bounded batch; never download chat history."""

    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]

    def post(self, request, space_id):
        from chat_domain.models import Conversation, Message, MessageAlias

        if len(request.body) > 256 * 1024:
            return Response({"detail": "Key query is too large."}, status=413)
        space = get_object_or_404(Space, pk=space_id)
        if not SpacePermissionService.can_upload(request.user, space):
            return Response({"detail": "Space not found."}, status=404)
        data = request.data
        if not isinstance(data, dict) or set(data) != {"source_account_id", "queries"}:
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
            if not isinstance(query, dict) or set(query) != {"username", "keys"}:
                return Response({"detail": "Invalid key query."}, status=400)
            name, keys = query["username"], query["keys"]
            if (
                not isinstance(name, str)
                or not isinstance(keys, list)
                or any(not isinstance(k, str) or len(k) > 255 for k in keys)
            ):
                return Response({"detail": "Invalid message keys."}, status=400)
            total += len(keys)
            if total > 1000:
                return Response({"detail": "Too many message keys."}, status=400)
            conversations = list(
                Conversation.objects.filter(
                    space=space, platform="wechat", source_conversation_id=name
                )[:2]
            )
            if len(conversations) > 1:
                return Response({"detail": "Ambiguous conversation."}, status=409)
            found = []
            if conversations:
                c = conversations[0]
                # Canonical keys may belong to another source account. Namespace aliases
                # are authoritative for local src IDs after canonical consolidation.
                aliases = MessageAlias.objects.filter(
                    conversation=c, source_namespace=account, alias_key__in=keys
                ).select_related("message")
                found.extend(
                    {"message_key": a.alias_key, "occurred_at": a.message.occurred_at}
                    for a in aliases
                )
                alias_keys = {item["message_key"] for item in found}
                if c.source_namespace == account:
                    rows = Message.objects.filter(
                        conversation=c, message_key__in=set(keys) - alias_keys
                    )
                    found.extend(
                        {"message_key": m.message_key, "occurred_at": m.occurred_at}
                        for m in rows
                    )
            result.append({"username": name, "keys": found})
        return Response({"data": {"list": result}})


class DesktopConversationLookupAPIView(APIView):
    """Exact, lightweight lookup after the user opens locally missing records."""

    permission_classes = [IsAuthenticated]

    def get(self, request, space_id):
        from chat_domain.models import Conversation

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
        rows = list(
            Conversation.objects.filter(
                space=space, platform=platform, source_conversation_id=name
            )[:2]
        )
        if len(rows) > 1:
            return Response({"detail": "Ambiguous conversation."}, status=409)
        row = rows[0] if rows else None
        if (
            row
            and row.source_namespace != account
            and account not in row.metadata.get("source_namespaces", [])
        ):
            row = None
        return Response(
            {
                "data": {
                    "conversation": {"id": row.pk, "title": row.title} if row else None
                }
            }
        )

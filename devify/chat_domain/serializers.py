from rest_framework import serializers

from chat_domain.models import (
    Conversation,
    Message,
    MessageOrigin,
    MessagePart,
)

PART_PLACEHOLDERS = {
    MessagePart.Kind.IMAGE: "[图片]",
    MessagePart.Kind.VIDEO: "[视频]",
    MessagePart.Kind.AUDIO: "[语音]",
    MessagePart.Kind.FILE: "[文件]",
    MessagePart.Kind.QUOTE: "[引用]",
    MessagePart.Kind.FORWARDED_ITEM: "[转发]",
}
MEDIA_PART_KINDS = (
    MessagePart.Kind.IMAGE,
    MessagePart.Kind.VIDEO,
    MessagePart.Kind.AUDIO,
    MessagePart.Kind.FILE,
)


def avatar_url(space_id, sha256):
    """API-relative URL of one stored avatar, or an empty string.

    The path is relative to the API base (``/api``) so it keeps working
    behind a proxy that rewrites the host, and the desktop client can prefix
    its own base URL.
    """
    if not sha256:
        return ""
    return f"/v1/spaces/{space_id}/avatars/{sha256}"


def media_url(space_id, upload_item_id):
    """API-relative URL for one file inside a chat upload archive."""
    if not space_id or not upload_item_id:
        return ""
    return f"/v1/spaces/{space_id}/media/{upload_item_id}"


def message_preview(message, limit=280):
    """Flatten a message's parts into one readable line for list views."""
    if message is None:
        return ""
    chunks = []
    for part in message.parts.all():
        text = (part.text or "").strip()
        if text:
            chunks.append(text)
        elif part.kind in PART_PLACEHOLDERS:
            chunks.append(PART_PLACEHOLDERS[part.kind])
    preview = " ".join(chunks).strip()
    if len(preview) > limit:
        preview = preview[: limit - 1] + "…"
    return preview


class ConversationListSerializer(serializers.ModelSerializer):
    last_message_preview = serializers.SerializerMethodField()
    last_message_sender = serializers.SerializerMethodField()
    participant_count = serializers.IntegerField(read_only=True, default=0)
    event_count = serializers.IntegerField(read_only=True, default=0)
    pending_event_count = serializers.IntegerField(read_only=True, default=0)
    avatar_url = serializers.SerializerMethodField()

    def _latest_message(self, obj):
        return (self.context.get("latest_messages") or {}).get(obj.pk)

    def get_avatar_url(self, obj):
        avatar = getattr(obj, "avatar", None)
        if avatar is None:
            return ""
        return avatar_url(obj.space_id, avatar.sha256)

    def get_last_message_preview(self, obj):
        return message_preview(self._latest_message(obj))

    def get_last_message_sender(self, obj):
        message = self._latest_message(obj)
        if message is None:
            return ""
        return message.sender_name or message.sender_key or ""

    class Meta:
        model = Conversation
        fields = (
            "id",
            "space_id",
            "platform",
            "source_namespace",
            "source_conversation_id",
            "title",
            "kind",
            "timezone",
            "message_count",
            "participant_count",
            "event_count",
            "pending_event_count",
            "avatar_url",
            "last_message_at",
            "last_message_preview",
            "last_message_sender",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class ConversationDetailSerializer(ConversationListSerializer):
    class Meta(ConversationListSerializer.Meta):
        fields = ConversationListSerializer.Meta.fields + (
            "self_sender_key",
            "metadata",
        )
        read_only_fields = fields


class MessagePartSerializer(serializers.ModelSerializer):
    media_url = serializers.SerializerMethodField()
    media_content_type = serializers.SerializerMethodField()
    media_size = serializers.SerializerMethodField()

    def get_media_url(self, obj):
        if obj.kind not in (
            MessagePart.Kind.IMAGE,
            MessagePart.Kind.VIDEO,
            MessagePart.Kind.AUDIO,
            MessagePart.Kind.FILE,
        ) or obj.binding_state != MessagePart.BindingState.AVAILABLE:
            return ""
        item = obj.upload_item
        return media_url(self.context.get("space_id"), item.pk if item else None)

    def get_media_content_type(self, obj):
        return getattr(obj.upload_item, "content_type", "") if obj.upload_item else ""

    def get_media_size(self, obj):
        return getattr(obj.upload_item, "size", None) if obj.upload_item else None

    class Meta:
        model = MessagePart
        fields = (
            "id",
            "part_key",
            "parent_part_id",
            "ordinal",
            "kind",
            "text",
            "upload_item_id",
            "binding_state",
            "source_locator",
            "source_header",
            "media_url",
            "media_content_type",
            "media_size",
        )
        read_only_fields = fields


class MessageOriginSerializer(serializers.ModelSerializer):
    class Meta:
        model = MessageOrigin
        fields = (
            "id",
            "upload_item_id",
            "locator_key",
            "record_locator",
            "parser_version",
            "created_at",
        )
        read_only_fields = fields


class MessageMediaSerializer(serializers.ModelSerializer):
    """Media parts only, so list views can render attachments inline."""

    media_url = serializers.SerializerMethodField()

    def get_media_url(self, obj):
        if obj.binding_state != MessagePart.BindingState.AVAILABLE:
            return ""
        item = obj.upload_item
        space_id = self.context.get("space_id")
        return media_url(space_id, item.pk if item else None)

    class Meta:
        model = MessagePart
        fields = ("id", "kind", "media_url")
        read_only_fields = fields


class MessageListSerializer(serializers.ModelSerializer):
    preview = serializers.SerializerMethodField()
    sender_avatar_url = serializers.SerializerMethodField()
    media = serializers.SerializerMethodField()

    def get_preview(self, obj):
        return message_preview(obj)

    def get_media(self, obj):
        parts = [
            part for part in obj.parts.all() if part.kind in MEDIA_PART_KINDS
        ]
        if not parts:
            return []
        return MessageMediaSerializer(
            parts, many=True, context=self.context
        ).data

    def get_sender_avatar_url(self, obj):
        if not obj.sender_key:
            return ""
        avatar = (self.context.get("sender_avatars") or {}).get(
            obj.sender_key
        )
        if avatar is None:
            return ""
        return avatar_url(self.context.get("space_id"), avatar.sha256)

    class Meta:
        model = Message
        fields = (
            "id",
            "conversation_id",
            "message_key",
            "source_message_id",
            "record_kind",
            "sender_key",
            "sender_name",
            "direction",
            "occurred_at",
            "source_order",
            "ingest_seq",
            "target_source_id",
            "relation_kind",
            "normalization_state",
            "preview",
            "media",
            "sender_avatar_url",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class MessageDetailSerializer(MessageListSerializer):
    parts = MessagePartSerializer(many=True, read_only=True)
    origins = MessageOriginSerializer(many=True, read_only=True)

    class Meta(MessageListSerializer.Meta):
        fields = MessageListSerializer.Meta.fields + (
            "source_fields",
            "reply_to_id",
            "parts",
            "origins",
        )
        read_only_fields = fields

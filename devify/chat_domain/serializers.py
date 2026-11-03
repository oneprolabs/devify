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

    def _latest_message(self, obj):
        return (self.context.get("latest_messages") or {}).get(obj.pk)

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


class MessageListSerializer(serializers.ModelSerializer):
    preview = serializers.SerializerMethodField()

    def get_preview(self, obj):
        return message_preview(obj)

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

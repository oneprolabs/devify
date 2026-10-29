from rest_framework import serializers

from chat_domain.models import (
    Conversation,
    Message,
    MessageOrigin,
    MessagePart,
)


class ConversationListSerializer(serializers.ModelSerializer):
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

from django.contrib import admin

from chat_domain.models import (
    Conversation,
    Message,
    MessageOrigin,
    MessagePart,
)


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "space",
        "platform",
        "title",
        "kind",
        "message_count",
        "last_message_at",
    )
    list_filter = ("platform", "kind")
    search_fields = ("identity_key", "title", "source_conversation_id")
    readonly_fields = [field.name for field in Conversation._meta.fields]


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "conversation",
        "message_key",
        "record_kind",
        "direction",
        "occurred_at",
        "ingest_seq",
    )
    list_filter = ("record_kind", "direction", "normalization_state")
    search_fields = ("message_key", "source_message_id", "sender_key")
    readonly_fields = [field.name for field in Message._meta.fields]


@admin.register(MessagePart)
class MessagePartAdmin(admin.ModelAdmin):
    list_display = ("id", "message", "part_key", "kind", "ordinal")
    list_filter = ("kind", "binding_state")
    search_fields = ("part_key", "text")
    readonly_fields = [field.name for field in MessagePart._meta.fields]


@admin.register(MessageOrigin)
class MessageOriginAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "message",
        "upload_item",
        "locator_key",
        "parser_version",
    )
    search_fields = ("locator_key", "parser_version")
    readonly_fields = [field.name for field in MessageOrigin._meta.fields]

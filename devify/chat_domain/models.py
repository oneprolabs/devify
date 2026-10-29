from django.db import models

from chat_ingestion.models import UploadItem
from spaces.models import Space


class Conversation(models.Model):
    """A source content container (chat, group, mail or mail thread).

    Conversations are isolated by space. ``identity_key`` is the normalized
    ``platform + source namespace + source conversation id`` key; callers
    must never use a display title as the merge key.

    Media assets are not modeled in Devify yet, so message parts reference
    the upload item that carried the file plus a binding state. A ``file_id``
    link can be added once a shared file domain exists.
    """

    class Platform(models.TextChoices):
        WECHAT = "wechat", "WeChat"
        WHATSAPP = "whatsapp", "WhatsApp"
        LINE = "line", "LINE"
        EMAIL = "email", "Email"
        OTHER = "other", "Other"

    class Kind(models.TextChoices):
        GROUP = "group", "Group"
        DIRECT = "direct", "Direct"
        MAIL = "mail", "Mail"
        MAIL_THREAD = "mail_thread", "Mail thread"
        UNKNOWN = "unknown", "Unknown"

    space = models.ForeignKey(
        Space,
        on_delete=models.PROTECT,
        related_name="chat_conversations",
    )
    platform = models.CharField(max_length=20, choices=Platform.choices)
    source_namespace = models.CharField(max_length=255)
    source_conversation_id = models.CharField(max_length=255, blank=True)
    identity_key = models.CharField(max_length=700)
    title = models.CharField(max_length=500, blank=True)
    kind = models.CharField(
        max_length=20,
        choices=Kind.choices,
        default=Kind.UNKNOWN,
    )
    timezone = models.CharField(max_length=64, blank=True)
    self_sender_key = models.CharField(max_length=255, blank=True)
    message_count = models.PositiveBigIntegerField(default=0)
    last_message_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-last_message_at", "-id")
        constraints = [
            models.UniqueConstraint(
                fields=("space", "identity_key"),
                name="unique_chat_conversation_identity",
            ),
        ]
        indexes = [
            models.Index(fields=("space", "last_message_at", "id")),
        ]

    def __str__(self):
        return self.title or self.identity_key


class Message(models.Model):
    """One immutable source message inside a conversation."""

    class RecordKind(models.TextChoices):
        MESSAGE = "message", "Message"
        SYSTEM = "system", "System"
        EDIT = "edit", "Edit"
        REVOKE = "revoke", "Revoke"
        UNKNOWN = "unknown", "Unknown"

    class Direction(models.TextChoices):
        INCOMING = "incoming", "Incoming"
        OUTGOING = "outgoing", "Outgoing"
        UNKNOWN = "unknown", "Unknown"

    class RelationKind(models.TextChoices):
        REPLY = "reply", "Reply"
        EDIT = "edit", "Edit"
        REVOKE = "revoke", "Revoke"

    class NormalizationState(models.TextChoices):
        WAITING = "waiting", "Waiting"
        READY = "ready", "Ready"
        PARTIAL = "partial", "Partial"
        FAILED = "failed", "Failed"

    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    message_key = models.CharField(max_length=500)
    source_message_id = models.CharField(max_length=255, blank=True)
    record_kind = models.CharField(
        max_length=20,
        choices=RecordKind.choices,
        default=RecordKind.MESSAGE,
    )
    sender_key = models.CharField(max_length=255, blank=True)
    sender_name = models.CharField(max_length=255, blank=True)
    direction = models.CharField(
        max_length=20,
        choices=Direction.choices,
        default=Direction.UNKNOWN,
    )
    occurred_at = models.DateTimeField(null=True, blank=True)
    source_order = models.BigIntegerField(null=True, blank=True)
    ingest_seq = models.PositiveBigIntegerField()
    reply_to = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="replies",
    )
    target_source_id = models.CharField(max_length=255, blank=True)
    relation_kind = models.CharField(
        max_length=20,
        choices=RelationKind.choices,
        blank=True,
    )
    source_fields = models.JSONField(default=dict, blank=True)
    normalization_state = models.CharField(
        max_length=20,
        choices=NormalizationState.choices,
        default=NormalizationState.READY,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("ingest_seq", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("conversation", "message_key"),
                name="unique_chat_message_key",
            ),
            models.UniqueConstraint(
                fields=("conversation", "ingest_seq"),
                name="unique_chat_message_ingest_seq",
            ),
        ]
        indexes = [
            models.Index(fields=("conversation", "occurred_at", "id")),
            models.Index(fields=("conversation", "sender_key", "occurred_at")),
        ]

    def __str__(self):
        return self.message_key


class MessagePart(models.Model):
    """Ordered content inside a message: text, media, quote or forward."""

    class Kind(models.TextChoices):
        TEXT = "text", "Text"
        IMAGE = "image", "Image"
        VIDEO = "video", "Video"
        AUDIO = "audio", "Audio"
        FILE = "file", "File"
        QUOTE = "quote", "Quote"
        FORWARDED_ITEM = "forwarded_item", "Forwarded item"
        UNKNOWN = "unknown", "Unknown"

    class BindingState(models.TextChoices):
        AVAILABLE = "available", "Available"
        MISSING = "missing", "Missing"
        OMITTED = "omitted", "Omitted"
        UNSUPPORTED = "unsupported", "Unsupported"
        UNRESOLVED = "unresolved", "Unresolved"

    message = models.ForeignKey(
        Message,
        on_delete=models.CASCADE,
        related_name="parts",
    )
    part_key = models.CharField(max_length=255)
    parent_part = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="children",
    )
    ordinal = models.PositiveIntegerField(default=0)
    kind = models.CharField(max_length=20, choices=Kind.choices)
    text = models.TextField(blank=True)
    upload_item = models.ForeignKey(
        UploadItem,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="chat_message_parts",
    )
    binding_state = models.CharField(
        max_length=20,
        choices=BindingState.choices,
        default=BindingState.AVAILABLE,
    )
    source_locator = models.JSONField(default=dict, blank=True)
    source_header = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("ordinal", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("message", "part_key"),
                name="unique_chat_message_part_key",
            ),
        ]
        indexes = [
            models.Index(
                fields=("message", "parent_part", "ordinal", "id")
            ),
            models.Index(fields=("upload_item", "message")),
        ]

    def __str__(self):
        return self.part_key


class MessageOrigin(models.Model):
    """Where one normalized message was found in one upload item."""

    message = models.ForeignKey(
        Message,
        on_delete=models.CASCADE,
        related_name="origins",
    )
    upload_item = models.ForeignKey(
        UploadItem,
        on_delete=models.PROTECT,
        related_name="chat_message_origins",
    )
    locator_key = models.CharField(max_length=255)
    record_locator = models.JSONField(default=dict, blank=True)
    parser_version = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("id",)
        constraints = [
            models.UniqueConstraint(
                fields=("upload_item", "locator_key", "parser_version"),
                name="unique_chat_message_origin",
            ),
        ]
        indexes = [
            models.Index(fields=("message", "upload_item")),
        ]

    def __str__(self):
        return f"{self.message_id}@{self.upload_item_id}"

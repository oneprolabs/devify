import uuid

from chat_sources.models import Source
from django.conf import settings
from django.db import models

from spaces.models import Space


class UploadBatch(models.Model):
    class Status(models.TextChoices):
        CREATED = "created", "Created"
        UPLOADING = "uploading", "Uploading"
        PROCESSING = "processing", "Processing"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"

    class Trigger(models.TextChoices):
        SCHEDULED = "scheduled", "Scheduled"
        MANUAL = "manual", "Manual"
        UNKNOWN = "unknown", "Unknown"

    class SourceType(models.TextChoices):
        WECHAT = "wechat", "WeChat"
        WHATSAPP = "whatsapp", "WhatsApp"
        LINE = "line", "LINE"

    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    space = models.ForeignKey(
        Space, on_delete=models.PROTECT, related_name="chat_upload_batches"
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="chat_upload_batches",
    )
    source = models.ForeignKey(
        Source,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="upload_batches",
    )
    # The import run that produced this batch. The relation lives on this side
    # so chat_ingestion depends on chat_sources instead of both apps pointing
    # at each other; SourceImport still reaches its batch through the reverse
    # accessor of the same name.
    source_import = models.OneToOneField(
        "chat_sources.SourceImport",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="upload_batch",
    )
    source_type = models.CharField(max_length=20, choices=SourceType.choices)
    source_account_id = models.CharField(max_length=255, blank=True)
    # Captured from the desktop client's access token when the upload is
    # created. Web uploads leave it blank; it is only used to show which
    # device produced a sync record.
    device_id = models.CharField(max_length=100, blank=True)
    # Reported by the desktop client at upload time so a record still shows
    # its platform when the device row is missing (for example an upload made
    # before device binding existed).
    platform = models.CharField(max_length=40, blank=True)
    idempotency_key = models.CharField(max_length=255)
    archive_sha256 = models.CharField(max_length=64, blank=True)
    archive_size = models.PositiveBigIntegerField(null=True, blank=True)
    # Digest of the normalised content, not of the zip: two uploaders packing
    # the same conversation differently still get the same value, which is
    # what lets the server skip analysing identical data twice.
    content_sha256 = models.CharField(max_length=64, blank=True, db_index=True)
    conversation_digests = models.JSONField(default=dict, blank=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.CREATED
    )
    trigger = models.CharField(
        max_length=20, choices=Trigger.choices, default=Trigger.MANUAL
    )
    error_message = models.TextField(blank=True)
    message_count = models.PositiveIntegerField(default=0)
    duplicate_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    archive_received_at = models.DateTimeField(null=True, blank=True)
    parse_started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at", "-id")
        constraints = [
            models.UniqueConstraint(
                fields=("space", "uploaded_by", "idempotency_key"),
                name="unique_chat_upload_idempotency",
            )
        ]
        indexes = [
            models.Index(fields=("space", "status")),
            models.Index(fields=("uploaded_by", "created_at")),
        ]

    def __str__(self):
        return f"{self.uuid} ({self.status})"


class UploadItem(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ACCEPTED = "accepted", "Accepted"
        DUPLICATE = "duplicate", "Duplicate"
        FAILED = "failed", "Failed"

    batch = models.ForeignKey(
        UploadBatch, on_delete=models.CASCADE, related_name="items"
    )
    path = models.CharField(max_length=500)
    content_type = models.CharField(max_length=120, blank=True)
    size = models.PositiveBigIntegerField(null=True, blank=True)
    sha256 = models.CharField(max_length=64, blank=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    message_count = models.PositiveIntegerField(default=0)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("batch", "path"), name="unique_chat_upload_item_path"
            )
        ]

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from spaces.models import Space


class Source(models.Model):
    class ChannelType(models.TextChoices):
        EMAIL = "email", "Email"
        WECHAT = "wechat", "WeChat"
        WHATSAPP = "whatsapp", "WhatsApp"
        LINE = "line", "LINE"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        PAUSED = "paused", "Paused"
        DISABLED = "disabled", "Disabled"

    space = models.ForeignKey(
        Space,
        on_delete=models.PROTECT,
        related_name="chat_sources",
    )
    channel_type = models.CharField(max_length=20, choices=ChannelType.choices)
    provider = models.CharField(max_length=80)
    external_account_key = models.CharField(max_length=255)
    display_name = models.CharField(max_length=255)
    capabilities = models.JSONField(default=list, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_chat_sources",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="updated_chat_sources",
    )
    last_seen_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("display_name", "id")
        constraints = [
            models.UniqueConstraint(
                fields=(
                    "space",
                    "channel_type",
                    "provider",
                    "external_account_key",
                ),
                name="unique_chat_source_external_account",
            )
        ]
        indexes = [
            models.Index(fields=("space", "channel_type", "status")),
            models.Index(fields=("space", "provider", "external_account_key")),
        ]

    def clean(self):
        if not self.external_account_key.strip():
            raise ValidationError(
                {
                    "external_account_key": (
                        "An external account key is required."
                    )
                }
            )
        if not isinstance(self.capabilities, list):
            raise ValidationError({"capabilities": "Must be a list."})

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.display_name} ({self.channel_type})"


class SourceImport(models.Model):
    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        RUNNING = "running", "Running"
        COMPLETED = "completed", "Completed"
        PARTIAL = "partial", "Partial"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"

    space = models.ForeignKey(
        Space,
        on_delete=models.PROTECT,
        related_name="chat_source_imports",
    )
    source = models.ForeignKey(
        Source,
        on_delete=models.PROTECT,
        related_name="imports",
    )
    initiated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="chat_source_imports",
    )
    upload_batch = models.OneToOneField(
        "chat_ingestion.UploadBatch",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="source_import",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.QUEUED,
    )
    discovered_count = models.PositiveIntegerField(default=0)
    accepted_count = models.PositiveIntegerField(default=0)
    duplicate_count = models.PositiveIntegerField(default=0)
    failed_count = models.PositiveIntegerField(default=0)
    cursor = models.JSONField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at", "-id")
        indexes = [
            models.Index(fields=("space", "status", "created_at")),
            models.Index(fields=("source", "status", "created_at")),
        ]

    def clean(self):
        if self.source_id and self.space_id:
            if self.source.space_id != self.space_id:
                raise ValidationError(
                    {"source": "Source must belong to the import space."}
                )

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

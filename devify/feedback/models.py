import os
import uuid
from pathlib import Path

from django.conf import settings
from django.db import models


class Feedback(models.Model):
    class Status(models.TextChoices):
        RECEIVED = "received", "已收到"
        PROCESSING = "processing", "处理中"
        NEEDS_INFO = "needs_info", "待补充"
        RESOLVED = "resolved", "已解决"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE
    )
    client_id = models.UUIDField()
    fingerprint = models.CharField(max_length=64)
    category = models.CharField(max_length=24)
    description = models.TextField(max_length=5000)
    contact = models.CharField(max_length=200, blank=True)
    context = models.JSONField(default=dict)
    diagnostics = models.JSONField(default=dict)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.RECEIVED
    )
    reply = models.TextField(blank=True, max_length=5000)
    fix_version = models.CharField(max_length=64, blank=True)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assigned_feedbacks",
        limit_choices_to={"is_staff": True},
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "client_id"],
                name="feedback_user_client_unique",
            )
        ]
        verbose_name = "问题反馈"
        verbose_name_plural = "问题反馈"


class FeedbackAttachment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    feedback = models.ForeignKey(
        Feedback, on_delete=models.CASCADE, related_name="attachments"
    )
    mime_type = models.CharField(max_length=32)
    size = models.PositiveIntegerField()
    expired = models.BooleanField(default=False)

    @property
    def path(self):
        # Intentionally outside any public MEDIA/static directory.
        root = getattr(
            settings, "FEEDBACK_STORAGE_ROOT", None
        ) or os.environ.get("FEEDBACK_STORAGE_ROOT", "/opt/feedback")
        return Path(root) / str(self.id)

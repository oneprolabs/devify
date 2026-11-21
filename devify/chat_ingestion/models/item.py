"""Individual conversation items within an upload batch."""

from django.db import models

from chat_ingestion.models.batch import UploadBatch


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

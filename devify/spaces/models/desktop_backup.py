"""Desktop backup settings and mutation receipts."""

from django.conf import settings
from django.db import models

from spaces.models.space import Space


class DesktopBackupConfig(models.Model):
    """Client-owned settings mirror; does not authorize local data access."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE
    )
    space = models.ForeignKey(Space, on_delete=models.CASCADE)
    device_id = models.CharField(max_length=100)
    target = models.CharField(max_length=300)
    draft = models.JSONField(default=dict)
    completed = models.JSONField(default=dict)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("user", "space", "device_id", "target"),
                name="unique_desktop_backup_target",
            )
        ]


class DesktopConfigReceipt(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE
    )
    space = models.ForeignKey(Space, on_delete=models.CASCADE)
    device_id = models.CharField(max_length=100)
    mutation_id = models.CharField(max_length=100)
    digest = models.CharField(max_length=64)
    result = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("user", "space", "device_id", "mutation_id"),
                name="unique_desktop_config_request",
            )
        ]
        indexes = [models.Index(fields=("created_at",))]

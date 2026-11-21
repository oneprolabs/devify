"""Space creation policy and resource quotas."""

from django.conf import settings
from django.db import models

from spaces.models.space import Space


class SpacePolicy(models.Model):
    singleton_key = models.CharField(
        max_length=20,
        unique=True,
        default="default",
        editable=False,
    )
    allow_user_create_spaces = models.BooleanField(default=False)
    max_invited_users = models.PositiveIntegerField(null=True, blank=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_space_policies",
    )
    updated_at = models.DateTimeField(auto_now=True)


class SpaceQuota(models.Model):
    space = models.OneToOneField(
        Space, on_delete=models.CASCADE, related_name="quota"
    )
    max_members = models.PositiveIntegerField(null=True, blank=True)
    storage_limit_bytes = models.PositiveBigIntegerField(null=True, blank=True)
    daily_ai_calls = models.PositiveIntegerField(null=True, blank=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_space_quotas",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

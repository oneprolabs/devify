from django.conf import settings
from django.db import models


class Space(models.Model):
    class Kind(models.TextChoices):
        PERSONAL = "personal", "Personal"
        TEAM = "team", "Team"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        SUSPENDED = "suspended", "Suspended"
        ARCHIVED = "archived", "Archived"

    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140, unique=True)
    kind = models.CharField(max_length=20, choices=Kind.choices)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="owned_spaces",
    )
    personal_owner = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="personal_space",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_spaces",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("name", "id")

    def __str__(self):
        return self.name


class SpaceMembership(models.Model):
    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        MAINTAINER = "maintainer", "Maintainer"
        USER = "user", "User"
        GUEST = "guest", "Guest"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        INVITED = "invited", "Invited"
        REMOVED = "removed", "Removed"

    space = models.ForeignKey(
        Space,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="space_memberships",
    )
    role = models.CharField(max_length=20, choices=Role.choices)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
    )
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="space_invitations_sent",
    )
    joined_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("space", "user"),
                name="unique_space_membership",
            ),
        ]
        indexes = [
            models.Index(fields=("user", "status")),
            models.Index(fields=("space", "status", "role")),
        ]

    def __str__(self):
        return f"{self.user_id}@{self.space_id}:{self.role}"


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


class SpaceAuditLog(models.Model):
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="space_audit_events",
    )
    space = models.ForeignKey(
        Space,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
    )
    action = models.CharField(max_length=80)
    resource_type = models.CharField(max_length=80, blank=True)
    resource_id = models.CharField(max_length=80, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at", "-id")
        indexes = [
            models.Index(fields=("space", "created_at")),
            models.Index(fields=("actor", "created_at")),
        ]


class SpaceTakeover(models.Model):
    space = models.ForeignKey(
        Space,
        on_delete=models.CASCADE,
        related_name="takeovers",
    )
    admin = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="space_takeovers",
    )
    reason = models.TextField(max_length=500)
    active = models.BooleanField(default=True)
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=("space", "active")),
            models.Index(fields=("admin", "active")),
        ]


def default_chat_analysis_preferences():
    return {
        "event_granularity": "balanced",
        "summary_length": "standard",
        "summary_style": "concise",
        "conversation_types": ["direct", "group"],
        "lookback_days": 0,
        "auto_analyze": True,
    }


def canonicalize_chat_analysis_preferences(preferences):
    """Normalize valid conversation type sets without changing input data."""
    preferences = dict(preferences)
    types = preferences.get("conversation_types")
    if isinstance(types, list) and all(
        isinstance(value, str) and value in ("direct", "group")
        for value in types
    ):
        preferences["conversation_types"] = sorted(set(types))
    return preferences


def effective_chat_analysis_preferences(preferences):
    """Expose the compatibility flag without changing stored preferences."""
    return canonicalize_chat_analysis_preferences({
        **default_chat_analysis_preferences(),
        **(preferences if isinstance(preferences, dict) else {}),
        "auto_analyze": True,
    })


class SpaceWorkflowConfig(models.Model):
    """Space-owned AI processing defaults, separate from user preferences."""

    space = models.OneToOneField(
        Space, on_delete=models.CASCADE, related_name="workflow_config"
    )
    text_llm_config_uuid = models.UUIDField(null=True, blank=True)
    image_llm_config_uuid = models.UUIDField(null=True, blank=True)
    language = models.CharField(max_length=32, default="zh-CN")
    scene = models.CharField(max_length=80, default="chat")
    prompt_overrides = models.JSONField(default=dict, blank=True)
    chat_analysis_preferences = models.JSONField(
        default=default_chat_analysis_preferences
    )
    attachment_policy = models.CharField(max_length=32, default="available")
    auto_process = models.BooleanField(default=True)
    processing_paused = models.BooleanField(default=False)
    version = models.PositiveIntegerField(default=1)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_space_workflow_configs",
    )
    created_at = models.DateTimeField(auto_now_add=True)
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

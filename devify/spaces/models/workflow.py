"""Space workflow defaults and analysis preferences."""

from django.conf import settings
from django.db import models

from spaces.models.space import Space


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
    return canonicalize_chat_analysis_preferences(
        {
            **default_chat_analysis_preferences(),
            **(preferences if isinstance(preferences, dict) else {}),
            "auto_analyze": True,
        }
    )


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

"""Workflow settings and analysis preference validation."""

from rest_framework import serializers

from spaces.models import (
    SpaceWorkflowConfig,
    effective_chat_analysis_preferences,
)


class SpaceWorkflowConfigSerializer(serializers.ModelSerializer):
    chat_analysis_preferences = serializers.SerializerMethodField()

    def get_chat_analysis_preferences(self, obj):
        return effective_chat_analysis_preferences(
            obj.chat_analysis_preferences
        )

    class Meta:
        model = SpaceWorkflowConfig
        fields = (
            "space_id",
            "text_llm_config_uuid",
            "image_llm_config_uuid",
            "language",
            "scene",
            "prompt_overrides",
            "chat_analysis_preferences",
            "attachment_policy",
            "auto_process",
            "processing_paused",
            "version",
            "updated_by_id",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "space_id",
            "version",
            "updated_by_id",
            "created_at",
            "updated_at",
        )


class ChatAnalysisPreferencesSerializer(serializers.Serializer):
    event_granularity = serializers.ChoiceField(
        choices=("fine", "balanced", "coarse")
    )
    summary_length = serializers.ChoiceField(
        choices=("short", "standard", "detailed")
    )
    summary_style = serializers.ChoiceField(
        choices=("concise", "narrative", "actions")
    )
    conversation_types = serializers.ListField(
        child=serializers.ChoiceField(choices=("direct", "group")),
        allow_empty=False,
    )
    lookback_days = serializers.ChoiceField(choices=(0, 30, 90))
    auto_analyze = serializers.BooleanField()

    def validate_auto_analyze(self, value):
        if not value:
            raise serializers.ValidationError(
                "Disabling automatic analysis is not supported."
            )
        return value


class SpaceWorkflowConfigUpdateSerializer(serializers.Serializer):
    text_llm_config_uuid = serializers.UUIDField(
        required=False, allow_null=True
    )
    image_llm_config_uuid = serializers.UUIDField(
        required=False, allow_null=True
    )
    language = serializers.CharField(max_length=32, required=False)
    scene = serializers.CharField(max_length=80, required=False)
    prompt_overrides = serializers.DictField(required=False)
    chat_analysis_preferences = ChatAnalysisPreferencesSerializer(
        required=False
    )

    def validate_chat_analysis_preferences(self, value):
        required = set(ChatAnalysisPreferencesSerializer().fields)
        if set(value) != required:
            raise serializers.ValidationError(
                "All analysis preference fields are required."
            )
        return value

    attachment_policy = serializers.ChoiceField(
        choices=("available", "skip", "required"), required=False
    )
    auto_process = serializers.BooleanField(required=False)
    processing_paused = serializers.BooleanField(required=False)

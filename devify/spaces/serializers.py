from rest_framework import serializers

from spaces.models import (
    Space,
    SpaceMembership,
    SpaceQuota,
    SpaceWorkflowConfig,
    effective_chat_analysis_preferences,
)


class SpaceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Space
        fields = (
            "id",
            "name",
            "slug",
            "kind",
            "status",
            "created_at",
            "updated_at",
        )


class SpaceCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=120)
    slug = serializers.SlugField(max_length=140, required=False)


class SpaceUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=120, required=False)
    status = serializers.ChoiceField(
        choices=(Space.Status.ACTIVE, Space.Status.ARCHIVED),
        required=False,
    )


class SpacePolicySerializer(serializers.Serializer):
    allow_user_create_spaces = serializers.BooleanField(required=False)
    max_invited_users = serializers.IntegerField(
        min_value=0, allow_null=True, required=False
    )


class MemberInviteSerializer(serializers.Serializer):
    user_id = serializers.IntegerField(min_value=1)
    role = serializers.ChoiceField(
        choices=(
            SpaceMembership.Role.MAINTAINER,
            SpaceMembership.Role.USER,
            SpaceMembership.Role.GUEST,
        )
    )


class MemberRoleSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=SpaceMembership.Role.choices)


class OwnershipTransferSerializer(serializers.Serializer):
    user_id = serializers.IntegerField(min_value=1)


class TakeoverSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=500)
    owner_user_id = serializers.IntegerField(min_value=1, required=False)


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


class SpaceQuotaSerializer(serializers.ModelSerializer):
    class Meta:
        model = SpaceQuota
        fields = (
            "space_id",
            "max_members",
            "storage_limit_bytes",
            "daily_ai_calls",
            "updated_by_id",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "space_id",
            "updated_by_id",
            "created_at",
            "updated_at",
        )


class SpaceQuotaUpdateSerializer(serializers.Serializer):
    max_members = serializers.IntegerField(
        min_value=0, allow_null=True, required=False
    )
    storage_limit_bytes = serializers.IntegerField(
        min_value=0, allow_null=True, required=False
    )
    daily_ai_calls = serializers.IntegerField(
        min_value=0, allow_null=True, required=False
    )

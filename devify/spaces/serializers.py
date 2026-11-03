from rest_framework import serializers

from spaces.models import Space, SpaceMembership, SpaceWorkflowConfig, SpaceQuota


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
    class Meta:
        model = SpaceWorkflowConfig
        fields = ("space_id", "text_llm_config_uuid", "image_llm_config_uuid", "language", "scene", "prompt_overrides", "attachment_policy", "auto_process", "processing_paused", "version", "updated_by_id", "created_at", "updated_at")
        read_only_fields = ("space_id", "version", "updated_by_id", "created_at", "updated_at")

class SpaceWorkflowConfigUpdateSerializer(serializers.Serializer):
    text_llm_config_uuid = serializers.UUIDField(required=False, allow_null=True)
    image_llm_config_uuid = serializers.UUIDField(required=False, allow_null=True)
    language = serializers.CharField(max_length=32, required=False)
    scene = serializers.CharField(max_length=80, required=False)
    prompt_overrides = serializers.DictField(required=False)
    attachment_policy = serializers.ChoiceField(choices=("available", "skip", "required"), required=False)
    auto_process = serializers.BooleanField(required=False)
    processing_paused = serializers.BooleanField(required=False)


class SpaceQuotaSerializer(serializers.ModelSerializer):
    class Meta:
        model = SpaceQuota
        fields = ("space_id", "max_members", "storage_limit_bytes", "daily_ai_calls", "updated_by_id", "created_at", "updated_at")
        read_only_fields = ("space_id", "updated_by_id", "created_at", "updated_at")

class SpaceQuotaUpdateSerializer(serializers.Serializer):
    max_members = serializers.IntegerField(min_value=0, allow_null=True, required=False)
    storage_limit_bytes = serializers.IntegerField(min_value=0, allow_null=True, required=False)
    daily_ai_calls = serializers.IntegerField(min_value=0, allow_null=True, required=False)

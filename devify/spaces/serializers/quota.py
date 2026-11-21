"""Space quota representation and validation."""

from rest_framework import serializers

from spaces.models import SpaceQuota


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

"""Space policy and takeover validation."""

from rest_framework import serializers


class SpacePolicySerializer(serializers.Serializer):
    allow_user_create_spaces = serializers.BooleanField(required=False)
    max_invited_users = serializers.IntegerField(
        min_value=0, allow_null=True, required=False
    )


class TakeoverSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=500)
    owner_user_id = serializers.IntegerField(min_value=1, required=False)

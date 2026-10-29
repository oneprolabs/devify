from rest_framework import serializers

from spaces.models import Space, SpaceMembership


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

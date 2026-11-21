"""Invitation, role, and ownership validation."""

from rest_framework import serializers

from spaces.models import SpaceMembership


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

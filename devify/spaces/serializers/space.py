"""Space representation and lifecycle validation."""

from rest_framework import serializers

from spaces.models import Space


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

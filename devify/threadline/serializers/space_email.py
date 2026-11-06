from rest_framework import serializers

from threadline.models import EmailMessage


class SpaceEmailSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmailMessage
        fields = (
            "id", "uuid", "space_id", "subject", "sender", "recipients",
            "received_at", "summary_title", "summary_content",
            "summary_priority", "status", "created_at", "updated_at",
        )
        read_only_fields = fields


class SpaceEmailDetailSerializer(SpaceEmailSerializer):
    class Meta(SpaceEmailSerializer.Meta):
        fields = SpaceEmailSerializer.Meta.fields + (
            "text_content", "html_content", "summary_data", "llm_content",
        )
        read_only_fields = fields

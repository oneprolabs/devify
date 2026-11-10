from rest_framework import serializers

from threadline.models import EmailMessage


class SpaceEmailSerializer(serializers.ModelSerializer):
    mailbox_uuid = serializers.SerializerMethodField()
    mailbox_name = serializers.SerializerMethodField()

    class Meta:
        model = EmailMessage
        fields = (
            "id",
            "uuid",
            "space_id",
            "mailbox_uuid",
            "mailbox_name",
            "subject",
            "sender",
            "recipients",
            "received_at",
            "summary_title",
            "summary_content",
            "summary_priority",
            "status",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    def get_mailbox_uuid(self, obj):
        return str(obj.mailbox.uuid) if obj.mailbox_id else None

    def get_mailbox_name(self, obj):
        return obj.mailbox.display_name if obj.mailbox_id else ""


class SpaceEmailDetailSerializer(SpaceEmailSerializer):
    attachments = serializers.SerializerMethodField()

    class Meta(SpaceEmailSerializer.Meta):
        fields = SpaceEmailSerializer.Meta.fields + (
            "text_content",
            "html_content",
            "summary_data",
            "llm_content",
            "attachments",
        )
        read_only_fields = fields

    def get_attachments(self, obj):
        return [
            {
                "uuid": str(attachment.uuid),
                "filename": attachment.filename,
                "content_type": attachment.content_type,
                "file_size": attachment.file_size,
            }
            for attachment in obj.attachments.all()
        ]

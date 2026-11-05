from chat_sources.models import Source, SourceImport
from rest_framework import serializers


class SourceCreateSerializer(serializers.Serializer):
    channel_type = serializers.ChoiceField(choices=Source.ChannelType.choices)
    provider = serializers.CharField(max_length=80)
    external_account_key = serializers.CharField(max_length=255)
    display_name = serializers.CharField(max_length=255)
    metadata = serializers.DictField(required=False, default=dict)

    def validate_provider(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("provider is required.")
        return value

    def validate_external_account_key(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError(
                "external_account_key is required."
            )
        return value


class SourceUpdateSerializer(serializers.Serializer):
    display_name = serializers.CharField(max_length=255, required=False)
    status = serializers.ChoiceField(
        choices=Source.Status.choices,
        required=False,
    )
    metadata = serializers.DictField(required=False)


class SourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Source
        fields = (
            "id",
            "space_id",
            "channel_type",
            "provider",
            "external_account_key",
            "display_name",
            "capabilities",
            "metadata",
            "status",
            "created_by_id",
            "updated_by_id",
            "last_seen_at",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class SourceImportSerializer(serializers.ModelSerializer):
    upload_batch_id = serializers.SerializerMethodField()

    def get_upload_batch_id(self, obj):
        # The relation is owned by UploadBatch, so this is a reverse
        # one-to-one accessor that raises when no batch was attached.
        batch = getattr(obj, "upload_batch", None)
        return batch.pk if batch else None

    class Meta:
        model = SourceImport
        fields = (
            "id",
            "space_id",
            "source_id",
            "initiated_by_id",
            "upload_batch_id",
            "status",
            "discovered_count",
            "accepted_count",
            "duplicate_count",
            "failed_count",
            "cursor",
            "error_message",
            "started_at",
            "completed_at",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

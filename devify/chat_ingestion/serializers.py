from rest_framework import serializers

from chat_ingestion.models import UploadBatch, UploadItem


class UploadBatchCreateSerializer(serializers.Serializer):
    # The project-wide CamelCaseJSONParser inserts an underscore before digits,
    # so ``archive_sha256`` arrives as ``archive_sha_256``. Accept both
    # spellings instead of silently dropping the declared checksum.
    FIELD_ALIASES = {"archive_sha_256": "archive_sha256"}

    source_type = serializers.ChoiceField(
        choices=UploadBatch.SourceType.choices
    )
    source_account_id = serializers.CharField(
        max_length=255, required=False, allow_blank=True
    )
    trigger = serializers.ChoiceField(
        choices=UploadBatch.Trigger.choices,
        required=False,
        default=UploadBatch.Trigger.MANUAL,
    )
    device_id = serializers.CharField(
        max_length=100, required=False, allow_blank=True
    )
    device_label = serializers.CharField(
        max_length=120, required=False, allow_blank=True
    )
    platform = serializers.CharField(
        max_length=40, required=False, allow_blank=True
    )
    idempotency_key = serializers.CharField(max_length=255)
    archive_sha256 = serializers.RegexField(
        regex=r"^[0-9a-fA-F]{64}$", required=False, allow_blank=True
    )
    archive_size = serializers.IntegerField(
        min_value=0, required=False, allow_null=True
    )

    def to_internal_value(self, data):
        if hasattr(data, "items"):
            data = {
                self.FIELD_ALIASES.get(key, key): value
                for key, value in data.items()
            }
        return super().to_internal_value(data)


class UploadItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = UploadItem
        fields = (
            "id",
            "path",
            "content_type",
            "size",
            "sha256",
            "status",
            "message_count",
            "error_message",
        )
        read_only_fields = fields


class UploadBatchSerializer(serializers.ModelSerializer):
    items = UploadItemSerializer(many=True, read_only=True)
    space_id = serializers.IntegerField(read_only=True)
    source_id = serializers.IntegerField(read_only=True)
    uploaded_by_id = serializers.IntegerField(read_only=True)
    conversation_count = serializers.SerializerMethodField()
    image_count = serializers.SerializerMethodField()
    analysis_summary = serializers.SerializerMethodField()
    source_provider = serializers.SerializerMethodField()

    def get_conversation_count(self, obj):
        # Only the list endpoint counts this; a detail read has no total.
        return getattr(obj, "conversation_count", None)

    def get_image_count(self, obj):
        return getattr(obj, "image_count", None)

    def get_analysis_summary(self, obj):
        return getattr(obj, "analysis_summary", None)

    def get_source_provider(self, obj):
        return obj.source.provider if obj.source_id else ""

    class Meta:
        model = UploadBatch
        fields = (
            "id",
            "uuid",
            "space_id",
            "source_id",
            "uploaded_by_id",
            "source_type",
            "source_account_id",
            "source_provider",
            "device_id",
            "platform",
            "trigger",
            "idempotency_key",
            "archive_sha256",
            "archive_size",
            "content_sha256",
            "status",
            "error_message",
            "message_count",
            "duplicate_count",
            "conversation_count",
            "image_count",
            "analysis_summary",
            "items",
            "created_at",
            "updated_at",
            "archive_received_at",
            "parse_started_at",
            "worker_started_at",
            "completed_at",
        )
        read_only_fields = fields

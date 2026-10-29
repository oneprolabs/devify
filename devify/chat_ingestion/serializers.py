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
    uploaded_by_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = UploadBatch
        fields = (
            "id", "uuid", "space_id", "uploaded_by_id", "source_type",
            "source_account_id", "idempotency_key", "archive_sha256",
            "archive_size", "status", "error_message", "message_count",
            "duplicate_count", "items", "created_at", "updated_at",
            "completed_at",
        )
        read_only_fields = fields

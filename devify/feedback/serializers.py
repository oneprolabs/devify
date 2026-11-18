from rest_framework import serializers

from feedback.models import Feedback


class StrictSerializer(serializers.Serializer):
    def to_internal_value(self, data):
        if isinstance(data, dict) and set(data) - set(self.fields):
            raise serializers.ValidationError("包含不支持的诊断字段。")
        return super().to_internal_value(data)


class ContextSerializer(StrictSerializer):
    app_version = serializers.CharField(max_length=32)
    platform = serializers.ChoiceField(choices=["macos", "windows", "linux"])
    arch = serializers.CharField(max_length=32, required=False)
    os_version = serializers.CharField(
        max_length=64, required=False, allow_blank=True, default=""
    )
    wechat_version = serializers.CharField(
        max_length=64, required=False, allow_blank=True, default=""
    )
    page = serializers.CharField(max_length=32, required=False)
    related_batch_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        max_length=20,
        required=False,
    )


class EventSerializer(StrictSerializer):
    at = serializers.DateTimeField()
    module = serializers.ChoiceField(
        choices=["app", "auth", "upload", "wechat", "feedback", "ui"]
    )
    operation = serializers.ChoiceField(
        choices=[
            "start",
            "open",
            "submit",
            "success",
            "failure",
            "exception",
            "panic",
        ]
    )
    code = serializers.CharField(
        max_length=64, required=False, allow_blank=True
    )
    task_id = serializers.CharField(
        max_length=80, required=False, allow_blank=True
    )
    batch_id = serializers.IntegerField(required=False, min_value=1)
    request_id = serializers.RegexField(
        r"\A[A-Za-z0-9][A-Za-z0-9._-]{0,79}\Z", required=False
    )
    server_request_id = serializers.RegexField(
        r"\A[A-Za-z0-9][A-Za-z0-9._-]{0,79}\Z", required=False
    )
    http_status = serializers.IntegerField(
        min_value=100, max_value=599, required=False
    )
    duration_ms = serializers.IntegerField(required=False, min_value=0)


class DiagnosticsV1Serializer(StrictSerializer):
    schema_version = serializers.IntegerField(min_value=1, max_value=1)
    generated_at = serializers.DateTimeField()
    events = EventSerializer(many=True, max_length=1000)


class DiagnosticsV2Serializer(StrictSerializer):
    schema_version = serializers.IntegerField(min_value=2, max_value=2)
    generated_at = serializers.DateTimeField()
    # One greppable text line per record: time, level, event, content.
    lines = serializers.ListField(
        child=serializers.CharField(max_length=4000, trim_whitespace=False),
        max_length=1000,
    )


class DiagnosticsField(serializers.Field):
    """Accept both diagnostic shapes; version 1 is the structured event list
    sent by older clients, version 2 is the plain-text line list."""

    def to_internal_value(self, data):
        if not isinstance(data, dict):
            raise serializers.ValidationError("诊断内容格式无效。")
        version = data.get("schema_version")
        serializer_class = (
            DiagnosticsV2Serializer
            if version == 2
            else DiagnosticsV1Serializer
        )
        # Run validation directly: `is_valid(raise_exception=True)` would build
        # `serializer.errors`, which cannot represent StrictSerializer's bare
        # validation message.
        return serializer_class().run_validation(data)

    def to_representation(self, value):
        if value.get("schema_version") == 2:
            return DiagnosticsV2Serializer(value).data
        return DiagnosticsV1Serializer(value).data


class CreateFeedbackSerializer(StrictSerializer):
    client_id = serializers.UUIDField()
    category = serializers.ChoiceField(
        choices=["wechat", "backup", "upload", "login", "interface", "other"]
    )
    description = serializers.CharField(max_length=5000)
    contact = serializers.CharField(
        max_length=200, required=False, allow_blank=True, default=""
    )
    context = ContextSerializer()
    diagnostics = DiagnosticsField(required=False)


class UpdateFeedbackSerializer(serializers.ModelSerializer):
    class Meta:
        model = Feedback
        fields = ["status", "reply", "fix_version", "assigned_to"]

    def validate_assigned_to(self, user):
        if user is not None and not user.is_staff:
            raise serializers.ValidationError("只能分派给管理员。")
        return user


class AttachmentSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    size = serializers.IntegerField()
    mime_type = serializers.CharField()
    expired = serializers.BooleanField()
    download_path = serializers.SerializerMethodField()

    def get_download_path(self, obj):
        return f"/api/v1/feedbacks/{obj.feedback_id}/attachments/{obj.id}"


class FeedbackSerializer(serializers.ModelSerializer):
    attachments = AttachmentSerializer(many=True, read_only=True)
    submitted_by = serializers.CharField(
        source="user.username", read_only=True
    )

    class Meta:
        model = Feedback
        fields = [
            "id",
            "client_id",
            "category",
            "description",
            "contact",
            "context",
            "diagnostics",
            "status",
            "reply",
            "fix_version",
            "assigned_to",
            "submitted_by",
            "created_at",
            "updated_at",
            "attachments",
        ]

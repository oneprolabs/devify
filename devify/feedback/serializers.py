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


class DiagnosticsSerializer(StrictSerializer):
    schema_version = serializers.IntegerField(min_value=1, max_value=1)
    generated_at = serializers.DateTimeField()
    events = EventSerializer(many=True, max_length=1000)


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
    diagnostics = DiagnosticsSerializer(required=False)


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

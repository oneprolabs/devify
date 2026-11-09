from rest_framework import serializers

from chat_analysis.models import AnalysisJob


class AnalysisJobCreateSerializer(serializers.Serializer):
    conversation_id = serializers.IntegerField(min_value=1)
    request_key = serializers.CharField(max_length=255)
    start_seq = serializers.IntegerField(
        min_value=0,
        required=False,
        default=0,
    )
    end_seq = serializers.IntegerField(min_value=0)
    input_version = serializers.CharField(max_length=100)
    specification = serializers.DictField(required=False, default=dict)

    def validate_request_key(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("request_key is required.")
        return value

    def validate_input_version(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("input_version is required.")
        return value

    def validate(self, attrs):
        if attrs["end_seq"] < attrs["start_seq"]:
            raise serializers.ValidationError(
                {"end_seq": "end_seq must be greater than start_seq."}
            )
        return attrs


class AnalysisJobSerializer(serializers.ModelSerializer):
    class Meta:
        model = AnalysisJob
        fields = (
            "id",
            "uuid",
            "space_id",
            "created_by_id",
            "conversation_id",
            "request_key",
            "start_seq",
            "end_seq",
            "input_version",
            "state",
            "checkpoint",
            "specification",
            "result_ref",
            "lease_owner",
            "lease_until",
            "fencing_token",
            "attempts",
            "error",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

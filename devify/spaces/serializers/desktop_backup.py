"""Validate desktop backup configuration payloads."""

from rest_framework import serializers


class StrictSerializer(serializers.Serializer):
    def to_internal_value(self, data):
        if not isinstance(data, dict) or set(data) - set(self.fields):
            raise serializers.ValidationError(
                "Unknown or invalid configuration fields."
            )
        return super().to_internal_value(data)


class RangeSerializer(StrictSerializer):
    since = serializers.IntegerField(allow_null=True)
    until = serializers.IntegerField(allow_null=True)

    def validate(self, data):
        if (
            data["since"] is not None
            and data["until"] is not None
            and data["since"] >= data["until"]
        ):
            raise serializers.ValidationError("Invalid history range.")
        return data


class BackupSerializer(StrictSerializer):
    mode = serializers.ChoiceField(choices=("interval", "times", "manual"))
    times = serializers.ListField(
        child=serializers.RegexField(r"^([01][0-9]|2[0-3]):[0-5][0-9]$"),
        max_length=24,
    )
    window_enabled = serializers.BooleanField()
    window_mode = serializers.ChoiceField(choices=("allow", "deny"))
    window_start = serializers.RegexField(r"^([01][0-9]|2[0-3]):[0-5][0-9]$")
    window_end = serializers.RegexField(r"^([01][0-9]|2[0-3]):[0-5][0-9]$")
    days = serializers.ListField(
        child=serializers.IntegerField(min_value=0, max_value=6), max_length=7
    )
    wifi_only = serializers.BooleanField()
    attachments = serializers.ChoiceField(choices=("text", "images", "all"))


class PayloadSerializer(StrictSerializer):
    setup_state = serializers.ChoiceField(choices=("draft", "completed"))
    enabled = serializers.BooleanField()
    usernames = serializers.ListField(
        child=serializers.CharField(max_length=255), max_length=1000
    )
    initial_ranges = serializers.DictField(child=RangeSerializer())
    sync_interval_seconds = serializers.IntegerField(
        min_value=60, max_value=3596400
    )
    backup = BackupSerializer()

    def validate(self, data):
        if set(data["initial_ranges"]) - set(data["usernames"]):
            raise serializers.ValidationError(
                "History ranges must belong to selected conversations."
            )
        return data


class TargetSerializer(StrictSerializer):
    platform = serializers.ChoiceField(choices=("wechat", "whatsapp"))
    source_account_id = serializers.CharField(max_length=255)


class SaveSerializer(StrictSerializer):
    schema_version = serializers.IntegerField(min_value=1, max_value=1)
    device_id = serializers.CharField(max_length=100)
    mutation_id = serializers.CharField(max_length=100)
    local_revision = serializers.IntegerField(min_value=0)
    target = TargetSerializer()
    payload = PayloadSerializer()

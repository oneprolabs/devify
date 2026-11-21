"""Validate summary requests and serialize saved snapshots."""

from datetime import timedelta

from rest_framework import serializers

from chat_analysis.models import ChatSummary
from chat_analysis.summaries.prompts import LANGUAGES, pinned_snapshot


class InputMessage(serializers.Serializer):
    username = serializers.CharField(max_length=200)
    display = serializers.CharField(max_length=500)
    sender = serializers.CharField(max_length=500, allow_blank=True)
    time = serializers.IntegerField(min_value=1)
    text = serializers.CharField(max_length=12000)


class SummaryCreate(serializers.Serializer):
    request_key = serializers.UUIDField()
    platform = serializers.ChoiceField(choices=["wechat", "whatsapp"])
    source_namespace = serializers.CharField(max_length=160)
    source_conversation_id = serializers.CharField(max_length=200)
    title = serializers.CharField(max_length=500)
    range_label = serializers.CharField(max_length=120)
    mode = serializers.ChoiceField(choices=["time", "pick"])
    period_start = serializers.DateTimeField()
    period_end = serializers.DateTimeField()
    language = serializers.ChoiceField(choices=LANGUAGES, default="中文")
    prompt_version = serializers.CharField(max_length=80, required=False)
    prompt_digest = serializers.RegexField(r"^[0-9a-f]{64}$", required=False)
    messages = InputMessage(many=True, allow_empty=False, max_length=2000)

    def validate(self, attrs):
        if ("prompt_version" in attrs) != ("prompt_digest" in attrs):
            raise serializers.ValidationError(
                "prompt_version 和 prompt_digest 必须同时提供。"
            )
        start, end = attrs["period_start"], attrs["period_end"]
        if start > end or end - start > timedelta(days=7):
            raise serializers.ValidationError(
                "单次总结的时间范围不能超过一周。"
            )
        messages = attrs["messages"]
        if sum(len(item["text"]) for item in messages) > 120000:
            raise serializers.ValidationError(
                "消息内容过多，请缩小时间范围或减少选择。"
            )
        if len({item["username"] for item in messages}) > 8:
            raise serializers.ValidationError("单次最多总结 8 个聊天。")
        if not any(
            item["username"] == attrs["source_conversation_id"]
            for item in messages
        ):
            raise serializers.ValidationError("总结必须包含当前会话的消息。")
        if any(
            not start.timestamp() <= item["time"] <= end.timestamp()
            for item in messages
        ):
            raise serializers.ValidationError("所选消息不在本次时间范围内。")
        return attrs


class SummaryOutput(serializers.ModelSerializer):
    prompt_version = serializers.SerializerMethodField()
    prompt_digest = serializers.SerializerMethodField()

    def get_prompt_version(self, record):
        return pinned_snapshot(record.prompt_snapshot)["version"]

    def get_prompt_digest(self, record):
        return pinned_snapshot(record.prompt_snapshot)["sha256"]

    class Meta:
        model = ChatSummary
        fields = [
            "id",
            "request_key",
            "platform",
            "source_namespace",
            "source_conversation_id",
            "title",
            "range_label",
            "mode",
            "period_start",
            "period_end",
            "sessions",
            "message_count",
            "status",
            "body",
            "error",
            "model",
            "prompt_version",
            "prompt_digest",
            "created_at",
            "updated_at",
        ]

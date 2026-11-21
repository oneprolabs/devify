"""Validate summary requests and serialize saved snapshots."""

import re
from datetime import timedelta

from rest_framework import serializers

from chat_analysis.models import ChatSummary
from chat_analysis.summaries.prompts import pinned_snapshot


class InputMessage(serializers.Serializer):
    """Validate one reviewed source message."""

    username = serializers.CharField(max_length=200)
    display = serializers.CharField(max_length=500)
    sender = serializers.CharField(max_length=500, allow_blank=True)
    time = serializers.IntegerField(min_value=1)
    text = serializers.CharField(max_length=12000)


class SummaryCreate(serializers.Serializer):
    """Accept output choices without exposing system-template editing."""

    request_key = serializers.UUIDField()
    platform = serializers.ChoiceField(choices=["wechat", "whatsapp"])
    source_namespace = serializers.CharField(max_length=160)
    source_conversation_id = serializers.CharField(max_length=200)
    title = serializers.CharField(max_length=500)
    range_label = serializers.CharField(max_length=120)
    mode = serializers.ChoiceField(choices=["time", "pick"])
    period_start = serializers.DateTimeField()
    period_end = serializers.DateTimeField()
    language = serializers.CharField(max_length=30, default="中文")
    scenario = serializers.CharField(max_length=40, required=False)
    instructions = serializers.CharField(
        max_length=4000, required=False, allow_blank=True
    )
    prompt_version = serializers.CharField(max_length=80, required=False)
    prompt_digest = serializers.RegexField(r"^[0-9a-f]{64}$", required=False)
    messages = InputMessage(many=True, allow_empty=False, max_length=2000)

    def validate_language(self, value):
        """Preserve client choices and accept standard language codes."""
        if value in {"中文", "English", "按原文语言", "auto"}:
            return value
        if re.fullmatch(r"[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*", value):
            return value
        raise serializers.ValidationError("Unsupported output language.")

    def validate(self, attrs):
        """Enforce the existing message and time-window admission limits."""
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
    """Expose user choices and provenance, keeping system rules private."""

    prompt_version = serializers.SerializerMethodField()
    prompt_digest = serializers.SerializerMethodField()
    scenario = serializers.SerializerMethodField()
    instructions = serializers.SerializerMethodField()

    def get_prompt_version(self, record):
        """Return the version used by this task, including legacy records."""
        return pinned_snapshot(record.prompt_snapshot)["version"]

    def get_prompt_digest(self, record):
        """Return the stored system-template digest."""
        return pinned_snapshot(record.prompt_snapshot)["sha256"]

    def get_scenario(self, record):
        """Leave unlabelled historical records unclassified."""
        return pinned_snapshot(record.prompt_snapshot).get("scenario")

    def get_instructions(self, record):
        """Return only the initiating user's supplementary requirements."""
        return pinned_snapshot(record.prompt_snapshot).get(
            "user_instructions", ""
        )

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
            "language",
            "scenario",
            "instructions",
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

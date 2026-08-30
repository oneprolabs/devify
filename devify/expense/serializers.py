"""Expense API serializers."""

from __future__ import annotations

from uuid import UUID

from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from expense.models import ExpenseAppConfig, ExpenseUserConfig


def _validate_string_list(value, field_label):
    if value in (None, ""):
        return []
    if not isinstance(value, list):
        raise serializers.ValidationError(
            _("%(field)s must be a list of strings.") % {"field": field_label}
        )
    cleaned = []
    for item in value:
        text = str(item or "").strip()
        if text:
            cleaned.append(text)
    return list(dict.fromkeys(cleaned))


class ExpenseUserConfigSerializer(serializers.ModelSerializer):
    """User-facing switch and preferences."""

    class Meta:
        model = ExpenseUserConfig
        fields = [
            "enabled",
            "enabled_at",
            "last_scanned_at",
            "home_city",
            "sender_allowlist",
            "keyword_filters",
            "filename_template",
            "extra_link_domains",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "enabled_at",
            "last_scanned_at",
            "created_at",
            "updated_at",
        ]

    def validate_sender_allowlist(self, value):
        return _validate_string_list(value, "sender_allowlist")

    def validate_keyword_filters(self, value):
        return _validate_string_list(value, "keyword_filters")

    def validate_extra_link_domains(self, value):
        return _validate_string_list(value, "extra_link_domains")


class ExpenseAppConfigSerializer(serializers.ModelSerializer):
    """Platform-level configuration, admin only."""

    llm_config_uuid = serializers.UUIDField(allow_null=True, required=False)
    text_llm_config_uuid = serializers.UUIDField(
        allow_null=True, required=False
    )

    class Meta:
        model = ExpenseAppConfig
        fields = [
            "id",
            "workflow_key",
            "llm_config_uuid",
            "text_llm_config_uuid",
            "scan_schedule",
            "max_pdf_pages",
            "link_domain_allowlist",
            "max_download_bytes",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "workflow_key", "created_at", "updated_at"]

    def validate_scan_schedule(self, value):
        schedule = str(value or "").strip()
        if len(schedule.split()) != 5:
            raise serializers.ValidationError(
                _("Scan schedule must be a 5-field cron expression.")
            )
        return schedule

    def validate_max_pdf_pages(self, value):
        if value < 1:
            raise serializers.ValidationError(
                _("Max PDF pages must be at least 1.")
            )
        return value

    def validate_link_domain_allowlist(self, value):
        return _validate_string_list(value, "link_domain_allowlist")

    def validate_llm_config_uuid(self, value):
        if value is not None and not isinstance(value, UUID):
            raise serializers.ValidationError(_("Invalid UUID"))
        return value

    def validate_text_llm_config_uuid(self, value):
        if value is not None and not isinstance(value, UUID):
            raise serializers.ValidationError(_("Invalid UUID"))
        return value

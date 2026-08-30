"""Expense API serializers."""

from __future__ import annotations

from uuid import UUID

from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from expense.models import (
    ExpenseAppConfig,
    ExpenseUserConfig,
    Invoice,
    InvoiceScanRun,
    InvoiceSourceFile,
)


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


class InvoiceScanRunSerializer(serializers.ModelSerializer):
    """Scan batch, with the credit figures the user cares about."""

    estimated_credits = serializers.SerializerMethodField()

    class Meta:
        model = InvoiceScanRun
        fields = [
            "uuid",
            "trigger",
            "status",
            "started_at",
            "finished_at",
            "emails_scanned",
            "candidate_emails",
            "links_fetched",
            "invoices_created",
            "duplicates",
            "not_invoice",
            "failed",
            "credits_consumed",
            "estimated_credits",
            "error_message",
        ]
        read_only_fields = fields

    def get_estimated_credits(self, obj) -> int:
        summary = (obj.details or {}).get("summary") or {}
        return summary.get("estimated_credits", 0)


class InvoiceScanRunDetailSerializer(InvoiceScanRunSerializer):
    """Adds the per-email verdicts behind the summary numbers."""

    class Meta(InvoiceScanRunSerializer.Meta):
        fields = InvoiceScanRunSerializer.Meta.fields + ["details"]
        read_only_fields = fields


class ScanRequestSerializer(serializers.Serializer):
    """Payload shared by the scan and preview endpoints."""

    lookback_days = serializers.IntegerField(
        required=False, allow_null=True, min_value=1, max_value=365
    )
    email_uuids = serializers.ListField(
        child=serializers.UUIDField(), required=False, allow_empty=False
    )

    def validate(self, attrs):
        if attrs.get("lookback_days") and attrs.get("email_uuids"):
            raise serializers.ValidationError(
                _("Provide either lookback_days or email_uuids, not both.")
            )
        return attrs


class InvoiceSourceFileSerializer(serializers.ModelSerializer):
    """A link found in an email body and what became of it."""

    class Meta:
        model = InvoiceSourceFile
        fields = [
            "uuid",
            "source_url",
            "final_url",
            "content_type",
            "file_size",
            "fetch_status",
            "user_allowed",
            "error_message",
            "fetched_at",
            "created_at",
        ]
        read_only_fields = fields


class InvoiceListSerializer(serializers.ModelSerializer):
    """Row shape for the invoice table."""

    email_subject = serializers.CharField(
        source="email_message.subject", read_only=True, default=""
    )

    class Meta:
        model = Invoice
        fields = [
            "uuid",
            "status",
            "invoice_type",
            "invoice_no",
            "issue_date",
            "seller_name",
            "total_amount",
            "tax_amount",
            "currency",
            "category",
            "category_source",
            "city",
            "needs_review",
            "confidence",
            "email_subject",
            "created_at",
        ]
        read_only_fields = fields


class InvoiceDetailSerializer(InvoiceListSerializer):
    """Everything the detail drawer shows, including provenance."""

    source_url = serializers.CharField(
        source="source_file.source_url", read_only=True, default=""
    )
    filename = serializers.CharField(
        source="email_attachment.filename", read_only=True, default=""
    )
    duplicate_of_uuid = serializers.CharField(
        source="duplicate_of.uuid", read_only=True, default=""
    )

    class Meta(InvoiceListSerializer.Meta):
        fields = InvoiceListSerializer.Meta.fields + [
            "invoice_code",
            "seller_tax_id",
            "buyer_name",
            "buyer_tax_id",
            "amount_excl_tax",
            "items",
            "ticket_details",
            "source_type",
            "source_url",
            "filename",
            "duplicate_of_uuid",
            "error_message",
            "updated_at",
        ]
        read_only_fields = fields


class InvoiceUpdateSerializer(serializers.ModelSerializer):
    """
    The fields a person may correct.

    Deliberately narrow: status, provenance and billing links are the
    system's to set, not the user's.
    """

    class Meta:
        model = Invoice
        fields = [
            "invoice_type",
            "invoice_no",
            "invoice_code",
            "issue_date",
            "seller_name",
            "seller_tax_id",
            "buyer_name",
            "buyer_tax_id",
            "total_amount",
            "tax_amount",
            "amount_excl_tax",
            "currency",
            "category",
            "city",
            "needs_review",
        ]

    def validate_total_amount(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError(
                _("Amount cannot be negative.")
            )
        return value


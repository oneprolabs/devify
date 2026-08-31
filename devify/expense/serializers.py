"""Expense API serializers."""

from __future__ import annotations

from uuid import UUID

from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from expense.models import (
    ExpenseAppConfig,
    ExpenseGroup,
    ExpenseUserConfig,
    Invoice,
    InvoiceScanRun,
    InvoiceSourceFile,
    TripSuggestion,
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


# What each kind of ticket is worth saying on one line, in reading order.
TICKET_LINE_KEYS = (
    "train_no",
    "flight_no",
    "from_station",
    "from_city",
    "to_station",
    "to_city",
    "seat_class",
    "cabin",
    "nights",
    "distance",
    "passenger",
)


def summarize_invoice(invoice) -> str:
    """
    The one line that tells a person what they are looking at.

    A row showing only the seller and the amount forces a click to tell two
    taxi rides apart, so the goods name and whatever the ticket carries -
    stations, flight number, nights - are folded into a single line here
    where the shapes of both JSON fields are known.
    """
    parts = []
    items = invoice.items if isinstance(invoice.items, list) else []
    for item in items[:2]:
        if isinstance(item, dict) and item.get("name"):
            parts.append(str(item["name"]).strip())

    details = (
        invoice.ticket_details
        if isinstance(invoice.ticket_details, dict)
        else {}
    )
    route = [details.get(key) for key in ("from_station", "from_city")]
    origin = next((value for value in route if value), "")
    arrive = [details.get(key) for key in ("to_station", "to_city")]
    destination = next((value for value in arrive if value), "")
    if origin and destination:
        parts.append(f"{origin} → {destination}")

    for key in TICKET_LINE_KEYS:
        if key in ("from_station", "from_city", "to_station", "to_city"):
            continue
        value = details.get(key)
        if value:
            parts.append(f"{value} 晚" if key == "nights" else str(value))

    # The clock time is what tells two taxi rides on the same day apart.
    # The date is already on the row, so only the time is worth repeating.
    clock = _clock_time(details.get("depart_at") or details.get("start_at"))
    if clock:
        parts.append(clock)

    return " · ".join(parts)


def _clock_time(value) -> str:
    text = str(value or "").strip()
    if len(text) >= 16 and ":" in text[10:]:
        return text[11:16]
    return ""


class InvoiceListSerializer(serializers.ModelSerializer):
    """Row shape for the invoice list."""

    email_subject = serializers.CharField(
        source="email_message.subject", read_only=True, default=""
    )
    summary_line = serializers.SerializerMethodField()

    class Meta:
        model = Invoice
        fields = [
            "uuid",
            "status",
            "invoice_type",
            "invoice_no",
            "issue_date",
            "expense_date",
            "seller_name",
            "buyer_name",
            "buyer_tax_id",
            "total_amount",
            "tax_amount",
            "currency",
            "category",
            "category_source",
            "city",
            "needs_review",
            "confidence",
            "disposition",
            "filed_reason",
            "summary_line",
            "email_subject",
            "created_at",
        ]
        read_only_fields = fields

    def get_summary_line(self, obj) -> str:
        return summarize_invoice(obj)


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


class ExpenseGroupSerializer(serializers.ModelSerializer):
    """A reimbursement batch with its cached totals."""

    class Meta:
        model = ExpenseGroup
        fields = [
            "uuid",
            "name",
            "purpose",
            "status",
            "trip_type",
            "period_start",
            "period_end",
            "external_ref",
            "note",
            "invoice_count",
            "total_amount",
            "tax_amount",
            "exported_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "uuid",
            "period_start",
            "period_end",
            "invoice_count",
            "total_amount",
            "tax_amount",
            "exported_at",
            "created_at",
            "updated_at",
        ]

    def validate_name(self, value):
        name = str(value or "").strip()
        if not name:
            raise serializers.ValidationError(_("A name is required."))
        return name


class TripSuggestionSerializer(serializers.ModelSerializer):
    """An inferred business trip, offered rather than applied."""

    class Meta:
        model = TripSuggestion
        fields = [
            "uuid",
            "destination_city",
            "start_date",
            "end_date",
            "invoice_ids",
            "total_amount",
            "confidence",
            "status",
            "created_at",
        ]
        read_only_fields = fields


class GroupItemsSerializer(serializers.Serializer):
    """Invoices to add to or remove from a group."""

    invoice_uuids = serializers.ListField(
        child=serializers.UUIDField(), allow_empty=False
    )


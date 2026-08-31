"""Expense models for the invoice assistant application."""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from expense.constants import (
    DEFAULT_SCAN_SCHEDULE,
    WORKFLOW_KEY,
    ExpenseCategory,
)


class ExpenseAppConfig(models.Model):
    """Platform-level configuration, one row per workflow key."""

    workflow_key = models.CharField(
        max_length=64,
        unique=True,
        default=WORKFLOW_KEY,
        verbose_name=_("Workflow Key"),
    )
    llm_config_uuid = models.UUIDField(
        null=True,
        blank=True,
        verbose_name=_("Vision LLM Config UUID"),
        help_text=_(
            "Used for images and scanned documents without a text layer"
        ),
    )
    text_llm_config_uuid = models.UUIDField(
        null=True,
        blank=True,
        verbose_name=_("Text LLM Config UUID"),
        help_text=_("Used for PDF/OFD files that carry a usable text layer"),
    )
    scan_schedule = models.CharField(
        max_length=255,
        default=DEFAULT_SCAN_SCHEDULE,
        verbose_name=_("Scan Schedule"),
        help_text=_("5-field cron expression driving the periodic scan"),
    )
    max_pdf_pages = models.PositiveIntegerField(
        default=3,
        verbose_name=_("Max PDF Pages"),
    )
    link_domain_allowlist = models.JSONField(
        default=list,
        blank=True,
        verbose_name=_("Link Domain Allowlist"),
        help_text=_("Domains allowed for body-link downloads"),
    )
    max_download_bytes = models.PositiveIntegerField(
        default=20 * 1024 * 1024,
        verbose_name=_("Max Download Bytes"),
    )
    is_active = models.BooleanField(default=True, verbose_name=_("Active"))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Expense App Config")
        verbose_name_plural = _("Expense App Configs")

    def __str__(self) -> str:
        return self.workflow_key


class ExpenseUserConfig(models.Model):
    """Per-user switch and scan preferences."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="expense_config",
        verbose_name=_("User"),
    )
    enabled = models.BooleanField(default=False, verbose_name=_("Enabled"))
    enabled_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Enabled At"),
        help_text=_("Scans only look at mail received after this point"),
    )
    last_scanned_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Last Scanned At"),
    )
    home_city = models.CharField(
        max_length=64,
        blank=True,
        verbose_name=_("Home City"),
        help_text=_("Leave blank to infer from recent invoices"),
    )
    sender_allowlist = models.JSONField(
        default=list, blank=True, verbose_name=_("Sender Allowlist")
    )
    keyword_filters = models.JSONField(
        default=list, blank=True, verbose_name=_("Keyword Filters")
    )
    filename_template = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_("Filename Template"),
    )
    extra_link_domains = models.JSONField(
        default=list, blank=True, verbose_name=_("Extra Link Domains")
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Expense User Config")
        verbose_name_plural = _("Expense User Configs")
        indexes = [models.Index(fields=["enabled"])]

    def __str__(self) -> str:
        return f"{self.user_id} ({'on' if self.enabled else 'off'})"


class InvoiceSourceFile(models.Model):
    """
    A file fetched from a link in the email body.

    Kept separate from EmailAttachment on purpose: those rows describe files
    the sender attached, while these are files this app fetched itself, with
    a different trust level and cleanup policy.
    """

    class FetchStatus(models.TextChoices):
        OK = "ok", _("OK")
        BLOCKED_DOMAIN = "blocked_domain", _("Blocked Domain")
        BLOCKED_IP = "blocked_ip", _("Blocked IP")
        TOO_LARGE = "too_large", _("Too Large")
        TIMEOUT = "timeout", _("Timeout")
        REQUIRES_AUTH = "requires_auth", _("Requires Auth")
        BAD_TYPE = "bad_type", _("Bad Content Type")
        FAILED = "failed", _("Failed")

    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="invoice_source_files",
        verbose_name=_("User"),
    )
    email_message = models.ForeignKey(
        "threadline.EmailMessage",
        on_delete=models.CASCADE,
        related_name="invoice_source_files",
        verbose_name=_("Email Message"),
    )
    source_url = models.URLField(max_length=1000, verbose_name=_("Source URL"))
    final_url = models.URLField(
        max_length=1000, blank=True, verbose_name=_("Final URL")
    )
    content_type = models.CharField(
        max_length=100, blank=True, verbose_name=_("Content Type")
    )
    file_size = models.PositiveIntegerField(
        default=0, verbose_name=_("File Size")
    )
    file_path = models.CharField(
        max_length=500, blank=True, verbose_name=_("File Path")
    )
    content_md5 = models.CharField(
        max_length=32, blank=True, db_index=True, verbose_name=_("Content MD5")
    )
    fetch_status = models.CharField(
        max_length=32,
        choices=FetchStatus.choices,
        default=FetchStatus.OK,
        db_index=True,
        verbose_name=_("Fetch Status"),
    )
    user_allowed = models.BooleanField(
        default=False,
        verbose_name=_("User Allowed"),
        help_text=_(
            "Set when the user releases a single link whose domain is not "
            "on the allowlist"
        ),
    )
    error_message = models.TextField(blank=True, verbose_name=_("Error"))
    fetched_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Invoice Source File")
        verbose_name_plural = _("Invoice Source Files")
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "fetch_status"])]

    def __str__(self) -> str:
        return self.source_url[:80]


class Invoice(models.Model):
    """A single recognized invoice or travel receipt."""

    class SourceType(models.TextChoices):
        ATTACHMENT = "attachment", _("Attachment")
        BODY_LINK = "body_link", _("Body Link")
        NESTED_EML = "nested_eml", _("Nested EML")

    class Status(models.TextChoices):
        PENDING = "pending", _("Pending")
        EXTRACTING = "extracting", _("Extracting")
        EXTRACTED = "extracted", _("Extracted")
        DUPLICATE = "duplicate", _("Duplicate")
        NOT_INVOICE = "not_invoice", _("Not An Invoice")
        FAILED = "failed", _("Failed")
        INSUFFICIENT_CREDITS = (
            "insufficient_credits",
            _("Insufficient Credits"),
        )
        LINK_REQUIRES_AUTH = "link_requires_auth", _("Link Requires Auth")
        PENDING_DEPENDENCY = "pending_dependency", _("Pending Dependency")

    class InvoiceType(models.TextChoices):
        VAT_SPECIAL = "vat_special", _("VAT Special Invoice")
        VAT_NORMAL = "vat_normal", _("VAT Normal Invoice")
        VAT_ELECTRONIC = "vat_electronic", _("VAT Electronic Invoice")
        TRAIN = "train", _("Train Ticket")
        FLIGHT_ITINERARY = "flight_itinerary", _("Flight Itinerary")
        COACH = "coach", _("Coach Ticket")
        TAXI = "taxi", _("Taxi Receipt")
        HOTEL = "hotel", _("Hotel Invoice")
        QUOTA = "quota", _("Quota Invoice")
        OTHER = "other", _("Other")

    class CategorySource(models.TextChoices):
        RULE = "rule", _("Ticket Type Rule")
        USER_RULE = "user_rule", _("User Rule")
        MODEL = "model", _("Model")
        USER = "user", _("User Correction")

    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="invoices",
        verbose_name=_("User"),
    )
    # The email is also the billing unit: one email costs one credit no
    # matter how many invoices it carries.
    email_message = models.ForeignKey(
        "threadline.EmailMessage",
        on_delete=models.CASCADE,
        related_name="invoices",
        verbose_name=_("Email Message"),
    )
    source_type = models.CharField(
        max_length=32,
        choices=SourceType.choices,
        default=SourceType.ATTACHMENT,
        verbose_name=_("Source Type"),
    )
    email_attachment = models.ForeignKey(
        "threadline.EmailAttachment",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invoices",
        verbose_name=_("Email Attachment"),
    )
    source_file = models.ForeignKey(
        InvoiceSourceFile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invoices",
        verbose_name=_("Source File"),
    )
    status = models.CharField(
        max_length=32,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
        verbose_name=_("Status"),
    )
    invoice_type = models.CharField(
        max_length=32,
        choices=InvoiceType.choices,
        blank=True,
        verbose_name=_("Invoice Type"),
    )
    invoice_no = models.CharField(
        max_length=64, blank=True, verbose_name=_("Invoice Number")
    )
    invoice_code = models.CharField(
        max_length=64, blank=True, verbose_name=_("Invoice Code")
    )
    issue_date = models.DateField(
        null=True, blank=True, verbose_name=_("Issue Date")
    )
    # When the money was actually spent, which is not always when the
    # invoice was written: a train ticket for July can be invoiced in
    # August. Grouping and date filters follow this, not the issue date.
    expense_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_("Expense Date"),
        help_text=_("Travel or consumption date; falls back to issue date"),
    )
    seller_name = models.CharField(
        max_length=255, blank=True, verbose_name=_("Seller Name")
    )
    seller_tax_id = models.CharField(
        max_length=64, blank=True, verbose_name=_("Seller Tax ID")
    )
    buyer_name = models.CharField(
        max_length=255, blank=True, verbose_name=_("Buyer Name")
    )
    buyer_tax_id = models.CharField(
        max_length=64, blank=True, verbose_name=_("Buyer Tax ID")
    )
    total_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name=_("Total Amount"),
    )
    tax_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name=_("Tax Amount"),
    )
    amount_excl_tax = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name=_("Amount Excluding Tax"),
    )
    currency = models.CharField(
        max_length=8, default="CNY", verbose_name=_("Currency")
    )
    category = models.CharField(
        max_length=32,
        choices=ExpenseCategory.CHOICES,
        blank=True,
        verbose_name=_("Category"),
    )
    category_source = models.CharField(
        max_length=16,
        choices=CategorySource.choices,
        blank=True,
        verbose_name=_("Category Source"),
    )
    city = models.CharField(
        max_length=64,
        blank=True,
        verbose_name=_("City"),
        help_text=_("Where the expense happened; drives trip clustering"),
    )
    items = models.JSONField(default=list, blank=True, verbose_name=_("Items"))
    ticket_details = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_("Ticket Details"),
        help_text=_("Non-standard ticket fields such as train or flight info"),
    )
    raw_extraction = models.JSONField(
        default=dict, blank=True, verbose_name=_("Raw Extraction")
    )
    confidence = models.FloatField(
        null=True, blank=True, verbose_name=_("Confidence")
    )
    needs_review = models.BooleanField(
        default=False, verbose_name=_("Needs Review")
    )
    verification_status = models.CharField(
        max_length=32,
        default="unverified",
        verbose_name=_("Verification Status"),
    )
    # Nullable on purpose: MySQL/MariaDB does not support partial indexes,
    # so the uniqueness below has to be expressed with NULLs (which never
    # collide) rather than a filtered constraint on empty strings.
    dedup_key = models.CharField(
        max_length=128,
        null=True,
        blank=True,
        default=None,
        verbose_name=_("Dedup Key"),
    )
    duplicate_of = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="duplicates",
        verbose_name=_("Duplicate Of"),
    )
    credits_transaction = models.ForeignKey(
        "billing.EmailCreditsTransaction",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invoices",
        verbose_name=_("Credits Transaction"),
    )
    error_message = models.TextField(blank=True, verbose_name=_("Error"))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Invoice")
        verbose_name_plural = _("Invoices")
        ordering = ["-issue_date", "-created_at"]
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["user", "issue_date"]),
            models.Index(fields=["user", "expense_date"]),
            models.Index(fields=["user", "category"]),
            models.Index(fields=["user", "city", "issue_date"]),
        ]
        constraints = [
            # Both constraints stay unconditional so MariaDB actually
            # enforces them; NULL values are what keeps not-yet-extracted
            # rows from colliding.
            models.UniqueConstraint(
                fields=["user", "dedup_key"],
                name="expense_invoice_user_dedup_uniq",
            ),
            models.UniqueConstraint(
                fields=["email_attachment"],
                name="expense_invoice_attachment_uniq",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.invoice_no or self.uuid} ({self.status})"


class CategoryRule(models.Model):
    """
    A remembered classification, sourced from a user correction.

    Layer 2 of the classification chain: once a user files a seller under a
    category, the next invoice from that seller skips the model entirely.
    """

    class MatchType(models.TextChoices):
        SELLER_NAME = "seller_name", _("Seller Name")
        SELLER_TAX_ID = "seller_tax_id", _("Seller Tax ID")
        INVOICE_TYPE = "invoice_type", _("Invoice Type")

    class CreatedFrom(models.TextChoices):
        USER_CORRECTION = "user_correction", _("User Correction")
        PRESET = "preset", _("Preset")

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="expense_category_rules",
        verbose_name=_("User"),
    )
    match_type = models.CharField(
        max_length=32,
        choices=MatchType.choices,
        default=MatchType.SELLER_NAME,
        verbose_name=_("Match Type"),
    )
    match_value = models.CharField(
        max_length=255, verbose_name=_("Match Value")
    )
    category = models.CharField(
        max_length=32,
        choices=ExpenseCategory.CHOICES,
        verbose_name=_("Category"),
    )
    hit_count = models.PositiveIntegerField(
        default=0, verbose_name=_("Hit Count")
    )
    created_from = models.CharField(
        max_length=32,
        choices=CreatedFrom.choices,
        default=CreatedFrom.USER_CORRECTION,
        verbose_name=_("Created From"),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Category Rule")
        verbose_name_plural = _("Category Rules")
        ordering = ["-updated_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "match_type", "match_value"],
                name="expense_category_rule_uniq",
            )
        ]

    def __str__(self) -> str:
        return f"{self.match_value} -> {self.category}"


class ExpenseGroup(models.Model):
    """A reimbursement batch the user submits as one claim."""

    class Status(models.TextChoices):
        DRAFT = "draft", _("Draft")
        SUBMITTED = "submitted", _("Submitted")
        REIMBURSED = "reimbursed", _("Reimbursed")
        ARCHIVED = "archived", _("Archived")

    class TripType(models.TextChoices):
        BUSINESS_TRIP = "business_trip", _("Business Trip")
        DAILY = "daily", _("Daily")

    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="expense_groups",
        verbose_name=_("User"),
    )
    name = models.CharField(max_length=255, verbose_name=_("Name"))
    purpose = models.TextField(blank=True, verbose_name=_("Purpose"))
    status = models.CharField(
        max_length=32,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
        verbose_name=_("Status"),
    )
    trip_type = models.CharField(
        max_length=32,
        choices=TripType.choices,
        default=TripType.DAILY,
        verbose_name=_("Trip Type"),
    )
    period_start = models.DateField(null=True, blank=True)
    period_end = models.DateField(null=True, blank=True)
    external_ref = models.CharField(
        max_length=128, blank=True, verbose_name=_("External Reference")
    )
    note = models.TextField(blank=True, verbose_name=_("Note"))
    invoice_count = models.PositiveIntegerField(default=0)
    total_amount = models.DecimalField(
        max_digits=14, decimal_places=2, default=0
    )
    tax_amount = models.DecimalField(
        max_digits=14, decimal_places=2, default=0
    )
    exported_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Expense Group")
        verbose_name_plural = _("Expense Groups")
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "name"], name="expense_group_user_name_uniq"
            )
        ]
        indexes = [models.Index(fields=["user", "status"])]

    def __str__(self) -> str:
        return self.name


class ExpenseGroupItem(models.Model):
    """Membership of one invoice in one reimbursement group."""

    group = models.ForeignKey(
        ExpenseGroup,
        on_delete=models.CASCADE,
        related_name="items",
        verbose_name=_("Group"),
    )
    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.CASCADE,
        related_name="group_items",
        verbose_name=_("Invoice"),
    )
    sort_order = models.IntegerField(default=0)
    note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Expense Group Item")
        verbose_name_plural = _("Expense Group Items")
        ordering = ["sort_order", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["group", "invoice"],
                name="expense_group_item_uniq",
            )
        ]

    def __str__(self) -> str:
        return f"{self.group_id}:{self.invoice_id}"


class TripSuggestion(models.Model):
    """A business trip inferred from the invoice timeline."""

    class Status(models.TextChoices):
        SUGGESTED = "suggested", _("Suggested")
        ACCEPTED = "accepted", _("Accepted")
        DISMISSED = "dismissed", _("Dismissed")

    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="trip_suggestions",
        verbose_name=_("User"),
    )
    destination_city = models.CharField(
        max_length=64, verbose_name=_("Destination City")
    )
    start_date = models.DateField(verbose_name=_("Start Date"))
    end_date = models.DateField(verbose_name=_("End Date"))
    invoice_ids = models.JSONField(default=list, blank=True)
    total_amount = models.DecimalField(
        max_digits=14, decimal_places=2, default=0
    )
    confidence = models.FloatField(default=0)
    status = models.CharField(
        max_length=32,
        choices=Status.choices,
        default=Status.SUGGESTED,
        db_index=True,
        verbose_name=_("Status"),
    )
    accepted_group = models.ForeignKey(
        ExpenseGroup,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="trip_suggestions",
        verbose_name=_("Accepted Group"),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Trip Suggestion")
        verbose_name_plural = _("Trip Suggestions")
        ordering = ["-start_date"]
        indexes = [models.Index(fields=["user", "status"])]

    def __str__(self) -> str:
        return f"{self.destination_city} {self.start_date}~{self.end_date}"


class InvoiceScanRun(models.Model):
    """Audit record for one scan batch."""

    class Trigger(models.TextChoices):
        SCHEDULED = "scheduled", _("Scheduled")
        MANUAL = "manual", _("Manual")
        BACKFILL = "backfill", _("Backfill")

    class Status(models.TextChoices):
        RUNNING = "running", _("Running")
        COMPLETED = "completed", _("Completed")
        FAILED = "failed", _("Failed")

    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="invoice_scan_runs",
        verbose_name=_("User"),
    )
    trigger = models.CharField(
        max_length=32,
        choices=Trigger.choices,
        default=Trigger.SCHEDULED,
        verbose_name=_("Trigger"),
    )
    status = models.CharField(
        max_length=32,
        choices=Status.choices,
        default=Status.RUNNING,
        db_index=True,
        verbose_name=_("Status"),
    )
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    emails_scanned = models.PositiveIntegerField(default=0)
    candidate_emails = models.PositiveIntegerField(default=0)
    links_fetched = models.PositiveIntegerField(default=0)
    invoices_created = models.PositiveIntegerField(default=0)
    duplicates = models.PositiveIntegerField(default=0)
    not_invoice = models.PositiveIntegerField(default=0)
    failed = models.PositiveIntegerField(default=0)
    credits_consumed = models.PositiveIntegerField(default=0)
    error_message = models.TextField(blank=True)
    details = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = _("Invoice Scan Run")
        verbose_name_plural = _("Invoice Scan Runs")
        ordering = ["-started_at"]
        indexes = [models.Index(fields=["user", "status"])]

    def __str__(self) -> str:
        return f"{self.user_id} {self.trigger} {self.started_at:%Y-%m-%d}"

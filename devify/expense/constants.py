"""Shared constants for the Expense app."""

from django.utils.translation import gettext_lazy as _

# Platform-level singleton key, mirrors RelayAppConfig.workflow_key.
WORKFLOW_KEY = "expense"

# Default scan cadence: once per day at 03:00. Operators can change this
# from the admin config API without a redeploy.
DEFAULT_SCAN_SCHEDULE = "0 3 * * *"

# Beat entry that fans out per-user scans.
SCAN_TASK_NAME = "expense-schedule-invoice-scan"
SCAN_TASK_PATH = "expense.tasks.scheduler.schedule_invoice_scan"

SCAN_SCHEDULE_ERROR = "Scan schedule must be a 5-field cron expression."


class ExpenseCategory(object):
    """
    First-level reimbursement categories.

    Aligned with the expense accounts most Chinese companies use. The values
    are stable identifiers; display names are translated in the UI.
    """

    TRANSPORT_LONG = "transport_long"
    TRANSPORT_LOCAL = "transport_local"
    ACCOMMODATION = "accommodation"
    MEALS = "meals"
    ENTERTAINMENT = "entertainment"
    OFFICE = "office"
    COMMUNICATION = "communication"
    TRAINING = "training"
    OTHER = "other"

    CHOICES = [
        (TRANSPORT_LONG, _("Long-distance Transport")),
        (TRANSPORT_LOCAL, _("Local Transport")),
        (ACCOMMODATION, _("Accommodation")),
        (MEALS, _("Meals")),
        (ENTERTAINMENT, _("Entertainment")),
        (OFFICE, _("Office Supplies")),
        (COMMUNICATION, _("Communication")),
        (TRAINING, _("Training")),
        (OTHER, _("Other")),
    ]


# Layer 1 of the classification chain: the ticket type alone determines the
# category, so these never need a model call.
INVOICE_TYPE_CATEGORY_MAP = {
    "train": ExpenseCategory.TRANSPORT_LONG,
    "flight_itinerary": ExpenseCategory.TRANSPORT_LONG,
    "coach": ExpenseCategory.TRANSPORT_LONG,
    "taxi": ExpenseCategory.TRANSPORT_LOCAL,
    "hotel": ExpenseCategory.ACCOMMODATION,
}


# Attachment gating for candidate filtering.
PDF_CONTENT_TYPES = {"application/pdf", "application/x-pdf"}
OFD_CONTENT_TYPES = {"application/ofd", "application/x-ofd"}

# Signature images and logos cluster below this size; invoices do not.
MIN_IMAGE_BYTES = 20 * 1024

# Default keyword set used when the user has not configured their own.
# Matching is case-insensitive against subject, body and attachment names.
DEFAULT_INVOICE_KEYWORDS = (
    "发票",
    "电子发票",
    "增值税",
    "行程单",
    "车票",
    "机票",
    "报销",
    "税号",
    "invoice",
    "receipt",
    "fapiao",
    "itinerary",
)

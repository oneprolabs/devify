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
XML_CONTENT_TYPES = {"application/xml", "text/xml"}

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


# Labels for exported filenames, zip folders and the pasteable summary.
#
# Deliberately plain strings rather than the translated choice labels. An
# archived file must keep the same name forever, so its name cannot depend
# on the viewer's language or on a translation catalog appearing later;
# and the summary block is Chinese throughout, so English category names
# inside it read as a defect.
CATEGORY_LABELS_CN = {
    ExpenseCategory.TRANSPORT_LONG: "长途交通",
    ExpenseCategory.TRANSPORT_LOCAL: "市内交通",
    ExpenseCategory.ACCOMMODATION: "住宿",
    ExpenseCategory.MEALS: "餐饮",
    ExpenseCategory.ENTERTAINMENT: "业务招待",
    ExpenseCategory.OFFICE: "办公用品",
    ExpenseCategory.COMMUNICATION: "通讯",
    ExpenseCategory.TRAINING: "会议培训",
    ExpenseCategory.OTHER: "其他",
}


# Invoice type names for the export manifest, fixed for the same reason.
INVOICE_TYPE_LABELS_CN = {
    "vat_special": "增值税专用发票",
    "vat_normal": "增值税普通发票",
    "vat_electronic": "增值税电子普通发票",
    "train": "铁路车票",
    "flight_itinerary": "航空行程单",
    "coach": "公路客票",
    "taxi": "出租车票",
    "hotel": "住宿发票",
    "quota": "定额发票",
    "other": "其他",
}


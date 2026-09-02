"""
Turn an invoice into a filename a finance team can read at a glance.

The template is deliberately data-driven: what a company wants in the name
varies, and hardcoding one layout would mean a code change per customer.
"""

from __future__ import annotations

import re

DEFAULT_TEMPLATE = "{index}_{issue_date}_{category}_{seller}_{amount}"

# The fields a user may put in an export filename.
#
# `required` fields cannot be switched off. Without who was paid and how
# much, two files in the same claim are indistinguishable, and a name built
# from the remaining fields alone is not worth reading.
FIELD_DEFS = (
    {"key": "index", "required": False},
    {"key": "issue_date", "required": False},
    {"key": "category", "required": False},
    {"key": "seller", "required": True},
    {"key": "amount", "required": True},
    {"key": "invoice_no", "required": False},
    {"key": "buyer", "required": False},
    {"key": "invoice_type", "required": False},
    {"key": "city", "required": False},
)

FIELD_KEYS = tuple(field["key"] for field in FIELD_DEFS)
REQUIRED_FIELDS = tuple(
    field["key"] for field in FIELD_DEFS if field["required"]
)

# Characters no common filesystem accepts, plus control characters.
ILLEGAL_CHARS = re.compile(r'[\\/:*?"<>|\x00-\x1f]')
WHITESPACE = re.compile(r"\s+")
# A run of separators left behind when a field was missing.
EMPTY_RUNS = re.compile(r"_{2,}")

MAX_SELLER_CHARS = 20
MAX_FILENAME_CHARS = 120

PLACEHOLDER = re.compile(r"\{(\w+)\}")


def sanitize(value: str) -> str:
    """Strip anything a filesystem would refuse, without losing meaning."""
    text = ILLEGAL_CHARS.sub("_", str(value or ""))
    text = WHITESPACE.sub("_", text).strip("_")
    return text


def invoice_fields(invoice, index=None) -> dict:
    from expense.constants import CATEGORY_LABELS_CN

    category = invoice.category or ""

    return {
        # Position within the export, so a claim reads in the order it was
        # filed. Only the export knows it, so it is passed in.
        "index": str(index) if index is not None else "",
        "issue_date": (
            invoice.issue_date.strftime("%Y%m%d") if invoice.issue_date else ""
        ),
        "category": CATEGORY_LABELS_CN.get(category, category),
        "seller": sanitize(invoice.seller_name)[:MAX_SELLER_CHARS],
        "amount": (
            f"{invoice.total_amount:.2f}"
            if invoice.total_amount is not None
            else ""
        ),
        "invoice_no": sanitize(invoice.invoice_no),
        "invoice_type": invoice.invoice_type or "",
        "city": sanitize(invoice.city),
        "buyer": sanitize(invoice.buyer_name)[:MAX_SELLER_CHARS],
    }


def extension_for(invoice) -> str:
    """Keep whatever the original file was; never convert."""
    source = invoice.email_attachment or invoice.source_file
    name = getattr(source, "filename", "") or getattr(source, "file_path", "")
    _, _, suffix = str(name).rpartition(".")
    suffix = sanitize(suffix).lower()
    return f".{suffix}" if suffix and len(suffix) <= 5 else ""


def template_from_fields(fields) -> str:
    """
    Turn a chosen field order into a template string.

    The stored format stays a template so the sanitising, truncation and
    collision handling all keep working unchanged, and a template written
    by hand still loads.
    """
    chosen = [key for key in fields if key in FIELD_KEYS]
    for required in REQUIRED_FIELDS:
        if required not in chosen:
            chosen.append(required)
    return "_".join("{%s}" % key for key in chosen)


def fields_from_template(template: str) -> list[str]:
    """Read a template back as the field list the picker shows."""
    found = [
        key
        for key in PLACEHOLDER.findall(template or "")
        if key in FIELD_KEYS
    ]
    return list(dict.fromkeys(found))


def render(
    invoice,
    template: str = "",
    taken: set[str] | None = None,
    index=None,
) -> str:
    """
    Build the filename for one invoice.

    Missing fields drop out with their separator rather than leaving a gap,
    because non-standard tickets routinely have no invoice number.
    """
    values = invoice_fields(invoice, index=index)
    body = PLACEHOLDER.sub(
        lambda match: sanitize(values.get(match.group(1), "")),
        template or DEFAULT_TEMPLATE,
    )

    body = EMPTY_RUNS.sub("_", body).strip("_")
    if not body:
        body = str(invoice.uuid)

    extension = extension_for(invoice)
    limit = MAX_FILENAME_CHARS - len(extension)
    body = body[:limit]

    name = body + extension
    if taken is None:
        return name

    # Two invoices can legitimately render the same name, and a zip with
    # duplicate entries silently loses files.
    if name not in taken:
        taken.add(name)
        return name

    for index in range(2, 1000):
        candidate = f"{body}-{index}{extension}"
        if candidate not in taken:
            taken.add(candidate)
            return candidate

    fallback = f"{body}-{invoice.uuid}{extension}"
    taken.add(fallback)
    return fallback

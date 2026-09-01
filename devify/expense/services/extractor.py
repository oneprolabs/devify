"""
Structured extraction: decoded content in, invoice fields out.

The model is asked to judge whether the document is an invoice at all
before it reports any fields, so a payslip or a newsletter attachment comes
back as a clean negative instead of a hallucinated invoice.
"""

from __future__ import annotations

import logging
from datetime import datetime
from decimal import Decimal, InvalidOperation

from core.tracking import LLMTracker
from expense.constants import INVOICE_TYPE_CATEGORY_MAP, ExpenseCategory
from expense.models import Invoice
from expense.prompts import CONTEXT_TEMPLATE, EXTRACTION_PROMPT
from expense.services.decoder import DecodeMode
from threadline.utils.llm import parse_json_response

logger = logging.getLogger(__name__)

# Amounts must add up. Anything beyond a rounding cent means the read is
# suspect, which is a far more reliable signal than the model's own score.
AMOUNT_TOLERANCE = Decimal("0.02")

# Below this the model is telling us it struggled; flag for human review.
LOW_CONFIDENCE = 0.7

VALID_INVOICE_TYPES = {choice for choice, _ in Invoice.InvoiceType.choices}
VALID_CATEGORIES = {value for value, _ in ExpenseCategory.CHOICES}


class ExtractionError(Exception):
    """The model call or its response could not be used."""


def build_context(email, filename: str) -> str:
    return CONTEXT_TEMPLATE.format(
        subject=(email.subject or "")[:200],
        sender=(email.sender or "")[:120],
        received_at=email.received_at.isoformat() if email.received_at else "",
        filename=filename or "",
    )


def build_messages(decoded, context: str) -> list[dict]:
    """One message shape for both the text and the vision path."""
    blocks: list[dict] = [{"type": "text", "text": context}]

    if decoded.mode == DecodeMode.TEXT:
        blocks.append(
            {
                "type": "text",
                "text": "Document text:\n" + decoded.text[:20000],
            }
        )
    else:
        for data_url in decoded.image_data_urls():
            blocks.append(
                {"type": "image_url", "image_url": {"url": data_url}}
            )

    return [
        {"role": "system", "content": EXTRACTION_PROMPT},
        {"role": "user", "content": blocks},
    ]


def call_model(decoded, context: str, model_uuid: str, node_name: str):
    """Send the document to the model that suits how it was decoded."""
    if not model_uuid:
        raise ExtractionError(
            "No LLM configured for the expense app; set it in admin config"
        )

    messages = build_messages(decoded, context)
    response, _usage = LLMTracker.call_messages_and_track(
        messages=messages,
        json_mode=True,
        node_name=node_name,
        model_uuid=str(model_uuid),
    )

    if isinstance(response, dict):
        return response
    if isinstance(response, str):
        parsed = parse_json_response(response)
        if isinstance(parsed, dict):
            return parsed
    raise ExtractionError("Model did not return a JSON object")


def _to_decimal(value):
    if value in (None, "", "-"):
        return None
    try:
        return Decimal(str(value).replace(",", "").replace("¥", "").strip())
    except (InvalidOperation, ValueError):
        return None


def _to_date(value):
    text = str(value or "").strip()
    if not text:
        return None

    # Travel dates often arrive with a time attached ("2026-07-20 06:52"),
    # so the date part is taken on its own.
    head = text.replace("T", " ").split(" ")[0]

    for candidate in (text, head):
        for pattern in ("%Y-%m-%d", "%Y/%m/%d", "%Y年%m月%d日", "%Y%m%d"):
            try:
                return datetime.strptime(candidate, pattern).date()
            except ValueError:
                continue
    return None


# Fields that say when the expense happened rather than when it was
# invoiced, in the order they should be trusted.
TRAVEL_DATE_KEYS = ("depart_at", "check_in", "start_at")


def resolve_expense_date(ticket_details: dict, issue_date):
    """
    Work out when the money was actually spent.

    A train ticket for July can be invoiced in August, and grouping by the
    issue date would then file the journey under the wrong month.
    """
    if isinstance(ticket_details, dict):
        for key in TRAVEL_DATE_KEYS:
            parsed = _to_date(ticket_details.get(key))
            if parsed:
                return parsed
    return issue_date


def _clean_text(value, limit: int) -> str:
    return str(value or "").strip()[:limit]


def resolve_category(
    invoice_type: str, model_category: str
) -> tuple[str, str]:
    """
    Classify, cheapest signal first.

    A train ticket is long-distance transport by definition, so the ticket
    type decides without asking anyone. Only genuinely ambiguous documents
    fall through to what the model proposed.
    """
    mapped = INVOICE_TYPE_CATEGORY_MAP.get(invoice_type)
    if mapped:
        return mapped, Invoice.CategorySource.RULE

    if model_category in VALID_CATEGORIES:
        return model_category, Invoice.CategorySource.MODEL

    return ExpenseCategory.OTHER, Invoice.CategorySource.MODEL


def check_amounts(total, tax, excl) -> bool:
    """
    Return True when the amounts are self-consistent.

    Unknown pieces cannot contradict anything, so a partially filled
    receipt is not treated as suspect.
    """
    if total is None or tax is None or excl is None:
        return True
    return abs((excl + tax) - total) <= AMOUNT_TOLERANCE


def normalize(raw: dict) -> dict:
    """Turn the model's JSON into fields the Invoice model accepts."""
    if not raw.get("is_invoice"):
        return {"is_invoice": False}

    invoice_type = str(raw.get("invoice_type") or "").strip()
    if invoice_type not in VALID_INVOICE_TYPES:
        invoice_type = Invoice.InvoiceType.OTHER

    total = _to_decimal(raw.get("total_amount"))
    tax = _to_decimal(raw.get("tax_amount"))
    excl = _to_decimal(raw.get("amount_excl_tax"))
    amounts_consistent = check_amounts(total, tax, excl)

    try:
        confidence = float(raw.get("confidence") or 0)
    except (TypeError, ValueError):
        confidence = 0.0

    category, category_source = resolve_category(
        invoice_type, str(raw.get("category") or "").strip()
    )

    items = raw.get("items")
    ticket_details = raw.get("ticket_details")
    if not isinstance(ticket_details, dict):
        ticket_details = {}
    issue_date = _to_date(raw.get("issue_date"))

    invoice_no = _clean_text(raw.get("invoice_no"), 64)
    seller_name = _clean_text(raw.get("seller_name"), 255)

    return {
        "is_invoice": True,
        "invoice_type": invoice_type,
        "invoice_no": invoice_no,
        "invoice_code": _clean_text(raw.get("invoice_code"), 64),
        "issue_date": issue_date,
        "expense_date": resolve_expense_date(ticket_details, issue_date),
        "seller_name": seller_name,
        "seller_tax_id": _clean_text(raw.get("seller_tax_id"), 64),
        "buyer_name": _clean_text(raw.get("buyer_name"), 255),
        "buyer_tax_id": _clean_text(raw.get("buyer_tax_id"), 64),
        "total_amount": total,
        "tax_amount": tax,
        "amount_excl_tax": excl,
        "currency": _clean_text(raw.get("currency"), 8) or "CNY",
        "city": _clean_text(raw.get("city"), 64),
        "category": category,
        "category_source": category_source,
        "items": items if isinstance(items, list) else [],
        "ticket_details": ticket_details,
        "confidence": confidence,
        "needs_review": (
            not amounts_consistent or confidence < LOW_CONFIDENCE
        ),
        "amounts_consistent": amounts_consistent,
    }


def extract(decoded, email, filename: str, model_uuid: str, node_name: str):
    """Run one document through the model and normalize the result."""
    context = build_context(email, filename)
    raw = call_model(decoded, context, model_uuid, node_name)
    normalized = normalize(raw)
    normalized["raw_extraction"] = raw
    return normalized

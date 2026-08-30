"""
Recognition for one email, including what it costs.

Billing rule: one email that yields at least one new invoice costs one
credit, however many invoices it turned out to carry. Everything else is
free — emails that hold no invoice, invoices already on file, and runs that
failed before producing anything.

The charge happens after the work, once the outcome is known. That ordering
is deliberate: a user never pays for a document the system misread as an
invoice, and a failed run needs no refund because it was never billed.
"""

from __future__ import annotations

import hashlib
import logging

from django.db import IntegrityError, transaction
from django.utils import timezone

from billing.models import EmailCreditsTransaction
from billing.services.config_service import get_credit_policy
from billing.services.credits_service import CreditsService
from expense.models import Invoice
from expense.services.candidate_filter import SourceKind, evaluate_email
from expense.services.config_service import get_app_config, get_user_config
from expense.services.decoder import DecodeError, decode_source
from expense.services.extractor import ExtractionError, extract

logger = logging.getLogger(__name__)

NODE_NAME = "expense_invoice_extract"


class Outcome:
    NOT_CANDIDATE = "not_candidate"
    INSUFFICIENT_CREDITS = "insufficient_credits"
    COMPLETED = "completed"


def cost_per_email() -> int:
    return get_credit_policy().get("invoice_email_cost_credits", 1)


def idempotency_key(email, force: bool = False) -> str:
    if force:
        stamp = int(timezone.now().timestamp())
        return f"invoice_email_{email.uuid}_retry_{stamp}"
    return f"invoice_email_{email.uuid}_extraction"


def already_charged(email) -> EmailCreditsTransaction | None:
    return EmailCreditsTransaction.objects.filter(
        idempotency_key=f"invoice_email_{email.uuid}_extraction"
    ).first()


def build_dedup_key(fields: dict, attachment) -> str:
    """
    Prefer the invoice number; fall back to the file's own fingerprint.

    Non-standard tickets often carry no number at all, and the same file
    forwarded twice is still the same expense.
    """
    invoice_no = (fields.get("invoice_no") or "").strip()
    if invoice_no:
        return invoice_no

    if attachment is not None and attachment.content_md5:
        return attachment.content_md5

    seed = "|".join(
        str(fields.get(key) or "")
        for key in ("seller_name", "issue_date", "total_amount")
    )
    return hashlib.md5(seed.encode("utf-8")).hexdigest()


def _model_for(decoded, app_config) -> str:
    """Text decodes go to the cheap model; only pixels need the vision one."""
    if decoded.mode == "text":
        return str(
            app_config.text_llm_config_uuid or app_config.llm_config_uuid or ""
        )
    return str(app_config.llm_config_uuid or "")


def _extract_one(email, attachment, app_config) -> dict:
    """Decode and read one attachment. Raises on unusable input."""
    decoded = decode_source(
        attachment.file_path,
        content_type=attachment.content_type,
        filename=attachment.filename,
        max_pages=app_config.max_pdf_pages,
    )
    if decoded.is_empty:
        raise DecodeError("Decoded document is empty")

    fields = extract(
        decoded,
        email,
        attachment.filename or "",
        _model_for(decoded, app_config),
        NODE_NAME,
    )
    fields["decoder"] = decoded.decoder
    return fields


def _persist(email, attachment, fields, source_type) -> tuple[Invoice, str]:
    """
    Store one result, resolving duplicates against what is already on file.

    Returns the row and what happened, so the caller can decide whether the
    email produced anything worth charging for.
    """
    defaults = {
        "user": email.user,
        "email_message": email,
        "source_type": source_type,
        "email_attachment": attachment,
        "raw_extraction": fields.get("raw_extraction") or {},
    }

    if not fields.get("is_invoice"):
        invoice, _ = Invoice.objects.update_or_create(
            email_attachment=attachment,
            defaults={
                **defaults,
                "status": Invoice.Status.NOT_INVOICE,
                "dedup_key": None,
            },
        )
        return invoice, "not_invoice"

    dedup_key = build_dedup_key(fields, attachment)
    existing = (
        Invoice.objects.filter(user=email.user, dedup_key=dedup_key)
        .exclude(email_attachment=attachment)
        .first()
    )

    payload = {
        **defaults,
        "status": Invoice.Status.EXTRACTED,
        "dedup_key": dedup_key,
        "invoice_type": fields["invoice_type"],
        "invoice_no": fields["invoice_no"],
        "invoice_code": fields["invoice_code"],
        "issue_date": fields["issue_date"],
        "seller_name": fields["seller_name"],
        "seller_tax_id": fields["seller_tax_id"],
        "buyer_name": fields["buyer_name"],
        "buyer_tax_id": fields["buyer_tax_id"],
        "total_amount": fields["total_amount"],
        "tax_amount": fields["tax_amount"],
        "amount_excl_tax": fields["amount_excl_tax"],
        "currency": fields["currency"],
        "city": fields["city"],
        "category": fields["category"],
        "category_source": fields["category_source"],
        "items": fields["items"],
        "ticket_details": fields["ticket_details"],
        "confidence": fields["confidence"],
        "needs_review": fields["needs_review"],
        "error_message": "",
    }

    if existing:
        payload["status"] = Invoice.Status.DUPLICATE
        payload["duplicate_of"] = existing
        # The duplicate must not claim the key the original already holds.
        payload["dedup_key"] = None

    try:
        with transaction.atomic():
            invoice, _ = Invoice.objects.update_or_create(
                email_attachment=attachment, defaults=payload
            )
    except IntegrityError:
        # Another worker claimed the same dedup key between the lookup and
        # the write. Whoever got there first owns it; this one is a copy.
        payload["status"] = Invoice.Status.DUPLICATE
        payload["dedup_key"] = None
        invoice, _ = Invoice.objects.update_or_create(
            email_attachment=attachment, defaults=payload
        )

    return invoice, (
        "duplicate"
        if invoice.status == Invoice.Status.DUPLICATE
        else "extracted"
    )


def _mark_failed(email, attachment, message, source_type) -> Invoice:
    invoice, _ = Invoice.objects.update_or_create(
        email_attachment=attachment,
        defaults={
            "user": email.user,
            "email_message": email,
            "source_type": source_type,
            "status": Invoice.Status.FAILED,
            "error_message": str(message)[:2000],
            "dedup_key": None,
        },
    )
    return invoice


def recognize_email(email, force: bool = False) -> dict:
    """
    Recognize every invoice in one email and bill for it once.

    Returns a stats dict the scan run aggregates.
    """
    app_config = get_app_config()
    user_config = get_user_config(email.user)
    attachments = list(email.attachments.all())

    verdict = evaluate_email(email, attachments, app_config, user_config)
    if not verdict.is_candidate:
        return {"outcome": Outcome.NOT_CANDIDATE}

    charge = already_charged(email)
    cost = cost_per_email()

    # Checking the balance up front avoids burning model calls the user
    # cannot pay for.
    if not charge and not CreditsService.check_credits(email.user_id, cost):
        by_id = {a.id: a for a in attachments}
        for source in verdict.sources:
            attachment = by_id.get(source.attachment_id)
            if attachment is not None:
                Invoice.objects.update_or_create(
                    email_attachment=attachment,
                    defaults={
                        "user": email.user,
                        "email_message": email,
                        "status": Invoice.Status.INSUFFICIENT_CREDITS,
                        "dedup_key": None,
                    },
                )
        return {"outcome": Outcome.INSUFFICIENT_CREDITS}

    stats = {
        "outcome": Outcome.COMPLETED,
        "extracted": 0,
        "duplicates": 0,
        "not_invoice": 0,
        "failed": 0,
        "skipped": 0,
        "credits_consumed": 0,
    }

    by_id = {a.id: a for a in attachments}
    for source in verdict.sources:
        if source.kind != SourceKind.ATTACHMENT:
            # Body-link downloads arrive in M4.
            stats["skipped"] += 1
            continue

        attachment = by_id.get(source.attachment_id)
        if attachment is None:
            continue

        settled = Invoice.objects.filter(
            email_attachment=attachment,
            status__in=[
                Invoice.Status.EXTRACTED,
                Invoice.Status.DUPLICATE,
                Invoice.Status.NOT_INVOICE,
            ],
        ).exists()
        if settled and not force:
            stats["skipped"] += 1
            continue

        try:
            fields = _extract_one(email, attachment, app_config)
        except (DecodeError, ExtractionError) as exc:
            logger.warning(
                "Invoice extraction failed for attachment %s: %s",
                attachment.id,
                exc,
            )
            _mark_failed(email, attachment, exc, source.kind)
            stats["failed"] += 1
            continue
        except Exception as exc:
            logger.exception(
                "Unexpected invoice extraction error for attachment %s",
                attachment.id,
            )
            _mark_failed(email, attachment, exc, source.kind)
            stats["failed"] += 1
            continue

        _, result = _persist(email, attachment, fields, source.kind)
        if result == "extracted":
            stats["extracted"] += 1
        elif result == "duplicate":
            stats["duplicates"] += 1
        else:
            stats["not_invoice"] += 1

    # One charge for the email, and only when it actually produced something
    # new. Duplicates and non-invoices stay free.
    if stats["extracted"] > 0 and (force or charge is None):
        try:
            transaction_record = CreditsService.consume_credits(
                user_id=email.user_id,
                amount=cost,
                reason="invoice_extraction",
                email_message_id=email.id,
                idempotency_key=idempotency_key(email, force=force),
            )
            stats["credits_consumed"] = cost
            Invoice.objects.filter(
                email_message=email, status=Invoice.Status.EXTRACTED
            ).update(credits_transaction=transaction_record)
        except Exception:
            logger.exception(
                "Failed to charge for email %s after extraction", email.id
            )

    return stats

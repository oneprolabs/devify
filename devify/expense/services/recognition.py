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
import os

from django.db import IntegrityError, transaction
from django.utils import timezone

from billing.models import EmailCreditsTransaction
from billing.services.config_service import get_credit_policy
from billing.services.credits_service import CreditsService
from expense.models import Invoice, InvoiceSourceFile
from expense.services.candidate_filter import (
    SkipReason,
    SourceKind,
    evaluate_email,
    resolve_allowed_domains,
)
from expense.services.classification import classify
from expense.services.config_service import get_app_config, get_user_config
from expense.services.decoder import DecodeError, decode_source
from expense.services.extractor import ExtractionError, extract
from expense.services.link_fetcher import (
    MAX_LINKS_PER_EMAIL,
    fetch_link,
)

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


def build_dedup_key(fields: dict, attachment, source_file=None) -> str:
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

    if source_file is not None and source_file.content_md5:
        return source_file.content_md5

    seed = "|".join(
        str(fields.get(key) or "")
        for key in ("seller_name", "issue_date", "total_amount")
    )
    return hashlib.md5(seed.encode("utf-8")).hexdigest()


def find_sibling(email, fields, lookup) -> Invoice | None:
    """
    Find the invoice this document is another copy of, within its email.

    Senders attach one expense several times over: the same invoice as PDF,
    OFD and XML, plus an itinerary for the same ride. Only some of those
    carry an invoice number, so the number-based key misses the rest and
    the same money lands in the list two or three times. Inside a single
    email an identical amount is the same expense, not a coincidence.
    """
    amount = fields.get("total_amount")
    if fields.get("invoice_no") or amount in (None, ""):
        return None

    return (
        Invoice.objects.filter(
            user=email.user,
            email_message=email,
            total_amount=amount,
            status=Invoice.Status.EXTRACTED,
        )
        .exclude(**lookup)
        .order_by("id")
        .first()
    )


def absorb_unnumbered_copies(invoice: Invoice) -> int:
    """
    Take over copies of this invoice that were read before it.

    ``find_sibling`` only looks backwards, so which document a sender put
    first decides the outcome: an itinerary read before its invoice keeps
    its own row and the money is counted twice. The numbered invoice is
    always the one to keep, so when it arrives late it collects the copies
    that came before it - and their travel date with them.
    """
    if not invoice.invoice_no or invoice.total_amount is None:
        return 0

    copies = list(
        Invoice.objects.filter(
            user_id=invoice.user_id,
            email_message_id=invoice.email_message_id,
            total_amount=invoice.total_amount,
            invoice_no="",
            status=Invoice.Status.EXTRACTED,
        ).exclude(pk=invoice.pk)
    )
    for copy in copies:
        lift_travel_date(
            invoice,
            {
                "expense_date": copy.expense_date,
                "issue_date": copy.issue_date,
            },
        )
        copy.status = Invoice.Status.DUPLICATE
        copy.duplicate_of = invoice
        copy.dedup_key = None
        copy.save(
            update_fields=[
                "status",
                "duplicate_of",
                "dedup_key",
                "updated_at",
            ]
        )
    return len(copies)


def lift_travel_date(invoice: Invoice, fields: dict) -> None:
    """
    Take the travel date from a copy that knows it.

    A taxi invoice is cut weeks after the ride, so the invoice alone dates
    the expense wrong. The itinerary attached to the same email carries the
    real date, and it is the one a claim should be filed under - so when
    the copy knows the journey and the invoice does not, the invoice
    inherits it before the copy is set aside.
    """
    travelled = fields.get("expense_date")
    if not travelled or travelled == fields.get("issue_date"):
        return
    if invoice.expense_date and invoice.expense_date != invoice.issue_date:
        return

    invoice.expense_date = travelled
    invoice.save(update_fields=["expense_date", "updated_at"])


def _model_for(decoded, app_config) -> str:
    """
    Pick the model for how this document was decoded.

    Both slots are optional. They exist so an operator can send extracted
    text to a cheap model and rendered pages to a multimodal one; leaving
    them empty falls back to the deployment's default config, the same way
    the rest of the pipeline behaves. Requiring them would refuse work the
    default model can perfectly well do.
    """
    if decoded.mode == "text":
        chosen = (
            app_config.text_llm_config_uuid or app_config.llm_config_uuid
        )
    else:
        chosen = (
            app_config.llm_config_uuid or app_config.text_llm_config_uuid
        )

    if chosen:
        return str(chosen)

    # A plain lookup, not `ensure_default_llm_config`: that helper seeds
    # threadline's workflow config as a side effect, and reading which
    # model to use here has no business rewriting another app's settings.
    from agentcore_metering.adapters.django.services.config_source import (
        get_default_llm_config_uuid,
    )

    return str(get_default_llm_config_uuid() or "")


def _extract_file(email, file_path, content_type, filename, app_config):
    """Decode and read one file. Raises on unusable input."""
    decoded = decode_source(
        file_path,
        content_type=content_type,
        filename=filename,
        max_pages=app_config.max_pdf_pages,
    )
    if decoded.is_empty:
        raise DecodeError("Decoded document is empty")

    fields = extract(
        decoded,
        email,
        filename or "",
        _model_for(decoded, app_config),
        NODE_NAME,
    )
    fields["decoder"] = decoded.decoder
    if fields.get("is_invoice"):
        classify(email.user, fields)
    return fields


def _extract_one(email, attachment, app_config) -> dict:
    return _extract_file(
        email,
        attachment.file_path,
        attachment.content_type,
        attachment.filename,
        app_config,
    )


def record_blocked_links(email, verdict) -> None:
    """
    Keep refused links visible.

    A user whose invoice never arrived needs to see that a link was found
    and why it was not followed, otherwise the app looks simply broken.
    """
    reason_map = {
        SkipReason.BLOCKED_DOMAIN: (
            InvoiceSourceFile.FetchStatus.BLOCKED_DOMAIN
        ),
        SkipReason.NOT_HTTPS: InvoiceSourceFile.FetchStatus.BLOCKED_DOMAIN,
    }
    for item in verdict.skipped:
        status = reason_map.get(item.reason)
        if not status or not item.url:
            continue
        InvoiceSourceFile.objects.get_or_create(
            user=email.user,
            email_message=email,
            source_url=item.url[:1000],
            defaults={"fetch_status": status, "error_message": item.reason},
        )


def _persist(
    email, fields, source_type, attachment=None, source_file=None
) -> tuple[Invoice, str]:
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
        "source_file": source_file,
        "raw_extraction": fields.get("raw_extraction") or {},
    }
    # An attachment is unique per invoice row; a fetched file is keyed by
    # the row it produced instead.
    lookup = (
        {"email_attachment": attachment}
        if attachment is not None
        else {"source_file": source_file}
    )

    if not fields.get("is_invoice"):
        invoice, _ = Invoice.objects.update_or_create(
            **lookup,
            defaults={
                **defaults,
                "status": Invoice.Status.NOT_INVOICE,
                "dedup_key": None,
            },
        )
        return invoice, "not_invoice"

    dedup_key = build_dedup_key(fields, attachment, source_file)
    existing = (
        Invoice.objects.filter(user=email.user, dedup_key=dedup_key)
        .exclude(**lookup)
        .first()
    )
    if existing is None:
        existing = find_sibling(email, fields, lookup)

    payload = {
        **defaults,
        "status": Invoice.Status.EXTRACTED,
        "dedup_key": dedup_key,
        "invoice_type": fields["invoice_type"],
        "invoice_no": fields["invoice_no"],
        "invoice_code": fields["invoice_code"],
        "issue_date": fields["issue_date"],
        "expense_date": fields["expense_date"],
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
        lift_travel_date(existing, fields)

    try:
        with transaction.atomic():
            invoice, _ = Invoice.objects.update_or_create(
                **lookup, defaults=payload
            )
    except IntegrityError:
        # Another worker claimed the same dedup key between the lookup and
        # the write. Whoever got there first owns it; this one is a copy.
        payload["status"] = Invoice.Status.DUPLICATE
        payload["dedup_key"] = None
        invoice, _ = Invoice.objects.update_or_create(
            **lookup, defaults=payload
        )

    if invoice.status == Invoice.Status.EXTRACTED:
        absorb_unnumbered_copies(invoice)

    return invoice, (
        "duplicate"
        if invoice.status == Invoice.Status.DUPLICATE
        else "extracted"
    )


def _mark_failed(
    email, message, source_type, attachment=None, source_file=None
) -> Invoice:
    lookup = (
        {"email_attachment": attachment}
        if attachment is not None
        else {"source_file": source_file}
    )
    invoice, _ = Invoice.objects.update_or_create(
        **lookup,
        defaults={
            "user": email.user,
            "email_message": email,
            "source_type": source_type,
            "email_attachment": attachment,
            "source_file": source_file,
            "status": Invoice.Status.FAILED,
            "error_message": str(message)[:2000],
            "dedup_key": None,
        },
    )
    return invoice


def _tally(stats: dict, result: str) -> None:
    if result == "extracted":
        stats["extracted"] += 1
    elif result == "duplicate":
        stats["duplicates"] += 1
    elif result == "not_invoice":
        stats["not_invoice"] += 1
    elif result == "failed":
        stats["failed"] += 1


def _handle_link(
    email, url, app_config, allowed_domains, force, stats
) -> str | None:
    """Fetch one linked file and read it, recording why if either fails."""
    record, _ = InvoiceSourceFile.objects.get_or_create(
        user=email.user,
        email_message=email,
        source_url=url[:1000],
    )

    already_read = Invoice.objects.filter(
        source_file=record,
        status__in=[
            Invoice.Status.EXTRACTED,
            Invoice.Status.DUPLICATE,
            Invoice.Status.NOT_INVOICE,
        ],
    ).exists()
    if already_read and not force:
        stats["skipped"] += 1
        return None

    outcome = fetch_link(
        url,
        email,
        allowed_domains,
        app_config.max_download_bytes,
        skip_allowlist=record.user_allowed,
    )

    record.fetch_status = outcome.status
    record.error_message = outcome.error
    record.final_url = outcome.final_url[:1000]
    record.content_type = outcome.content_type
    record.file_size = outcome.file_size
    record.file_path = outcome.file_path
    record.content_md5 = outcome.content_md5
    record.fetched_at = timezone.now()
    record.save()

    if not outcome.ok:
        stats["link_failures"] = stats.get("link_failures", 0) + 1
        return None

    stats["links_fetched"] = stats.get("links_fetched", 0) + 1

    try:
        fields = _extract_file(
            email,
            outcome.file_path,
            outcome.content_type,
            os.path.basename(outcome.file_path),
            app_config,
        )
    except (DecodeError, ExtractionError) as exc:
        _mark_failed(
            email, exc, SourceKind.BODY_LINK, source_file=record
        )
        return "failed"
    except Exception as exc:
        logger.exception("Unexpected error reading linked file %s", url)
        _mark_failed(
            email, exc, SourceKind.BODY_LINK, source_file=record
        )
        return "failed"

    _, result = _persist(
        email, fields, SourceKind.BODY_LINK, source_file=record
    )
    return result


def recognize_email(email, force: bool = False, bill: bool = True) -> dict:
    """
    Recognize every invoice in one email and bill for it once.

    ``bill=False`` is for the email workflow, which has already charged for
    this email: the invoice path replaces the generic one rather than
    running alongside it, so the user pays once either way.

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
    # cannot pay for. When the caller has already charged, the email is
    # paid for and there is nothing left to check.
    if bill and not charge and not CreditsService.check_credits(
        email.user_id, cost
    ):
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

    record_blocked_links(email, verdict)

    by_id = {a.id: a for a in attachments}
    allowed_domains = resolve_allowed_domains(app_config, user_config)
    links_done = 0

    for source in verdict.sources:
        if source.kind == SourceKind.BODY_LINK:
            if links_done >= MAX_LINKS_PER_EMAIL:
                stats["skipped"] += 1
                continue
            links_done += 1
            outcome = _handle_link(
                email, source.url, app_config, allowed_domains, force, stats
            )
            if outcome is not None:
                _tally(stats, outcome)
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
            _mark_failed(email, exc, source.kind, attachment=attachment)
            stats["failed"] += 1
            continue
        except Exception as exc:
            logger.exception(
                "Unexpected invoice extraction error for attachment %s",
                attachment.id,
            )
            _mark_failed(email, exc, source.kind, attachment=attachment)
            stats["failed"] += 1
            continue

        _, result = _persist(
            email, fields, source.kind, attachment=attachment
        )
        _tally(stats, result)

    # One charge for the email, and only when it actually produced something
    # new. Duplicates and non-invoices stay free.
    if bill and stats["extracted"] > 0 and (force or charge is None):
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

"""
Scan orchestration.

A scan resolves which emails are worth recognizing and records the verdict
as an ``InvoiceScanRun``. Recognition and billing arrive in M3; until then
a scan is observation only and never spends a credit.
"""

from __future__ import annotations

import logging
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from billing.services.config_service import get_credit_policy
from expense.models import InvoiceScanRun
from expense.services.candidate_filter import evaluate_email, resolve_keywords
from expense.services.config_service import get_app_config, get_user_config
from threadline.models import EmailMessage

logger = logging.getLogger(__name__)

# How many per-email verdicts to keep on the run record. Enough to explain
# a surprising result without turning the row into a log file.
MAX_RECORDED_EMAILS = 200


def cost_per_email() -> int:
    return get_credit_policy().get("invoice_email_cost_credits", 1)


def resolve_since(user_config, lookback_days: int | None = None):
    """
    Work out where this scan starts.

    Without an explicit lookback the floor is whichever is later: the last
    successful scan, or the moment the user switched the app on. That is
    what keeps a fresh switch-on from reaching over a whole mailbox.
    """
    if lookback_days:
        return timezone.now() - timedelta(days=lookback_days)

    floors = [
        value
        for value in (user_config.last_scanned_at, user_config.enabled_at)
        if value
    ]
    return max(floors) if floors else None


def collect_emails(user, since=None, email_uuids=None):
    """Emails in scope, newest first."""
    queryset = EmailMessage.objects.filter(user=user).filter(
        merged_into__isnull=True
    )
    if email_uuids:
        queryset = queryset.filter(uuid__in=email_uuids)
    elif since:
        queryset = queryset.filter(received_at__gte=since)
    return queryset.prefetch_related("attachments").order_by("-received_at")


def evaluate_scope(user, since=None, email_uuids=None):
    """
    Run the filter over the scope and return the verdicts.

    Pure computation: no database writes, no credits, no model calls.
    """
    app_config = get_app_config()
    user_config = get_user_config(user)
    keywords = resolve_keywords(user_config)

    candidates = []
    non_candidates = 0
    scanned = 0

    for email in collect_emails(user, since=since, email_uuids=email_uuids):
        scanned += 1
        verdict = evaluate_email(
            email,
            list(email.attachments.all()),
            app_config,
            user_config,
            keywords=keywords,
        )
        if verdict.is_candidate:
            candidates.append(verdict)
        else:
            non_candidates += 1

    return {
        "emails_scanned": scanned,
        "candidates": candidates,
        "non_candidates": non_candidates,
    }


def summarize(evaluation: dict) -> dict:
    """Shape the verdicts into the numbers a user reads before paying."""
    candidates = evaluation["candidates"]
    attachment_sources = 0
    link_sources = 0
    blocked_links = []
    pending_dependency = 0

    for candidate in candidates:
        for source in candidate.sources:
            if source.kind == "body_link":
                link_sources += 1
            else:
                attachment_sources += 1

    for candidate in candidates:
        for item in candidate.skipped:
            if item.reason == "pending_dependency":
                pending_dependency += 1
            elif item.reason in ("blocked_domain", "not_https"):
                blocked_links.append(item.as_dict())

    candidate_count = len(candidates)
    return {
        "emails_scanned": evaluation["emails_scanned"],
        "candidate_emails": candidate_count,
        "non_candidate_emails": evaluation["non_candidates"],
        "attachment_sources": attachment_sources,
        "link_sources": link_sources,
        "blocked_links": blocked_links,
        "pending_dependency_attachments": pending_dependency,
        "cost_credits_per_email": cost_per_email(),
        "estimated_credits": candidate_count * cost_per_email(),
    }


def preview_scan(user, lookback_days=None, email_uuids=None) -> dict:
    """
    Answer "what would this cost?" without touching anything.

    Nothing is written and nothing is charged, so the UI can show the price
    before the user commits.
    """
    user_config = get_user_config(user)
    since = resolve_since(user_config, lookback_days)
    evaluation = evaluate_scope(user, since=since, email_uuids=email_uuids)

    summary = summarize(evaluation)
    summary["since"] = since.isoformat() if since else None
    summary["candidates"] = [
        candidate.as_dict()
        for candidate in evaluation["candidates"][:MAX_RECORDED_EMAILS]
    ]
    return summary


def execute_scan(run: InvoiceScanRun, lookback_days=None, email_uuids=None):
    """Fill in a scan run with the verdicts for its scope."""
    user_config = get_user_config(run.user)
    since = resolve_since(user_config, lookback_days)

    try:
        evaluation = evaluate_scope(
            run.user, since=since, email_uuids=email_uuids
        )
    except Exception as exc:
        logger.exception("Expense scan run %s failed", run.uuid)
        run.status = InvoiceScanRun.Status.FAILED
        run.error_message = str(exc)
        run.finished_at = timezone.now()
        run.save(
            update_fields=["status", "error_message", "finished_at"]
        )
        raise

    summary = summarize(evaluation)
    run.emails_scanned = summary["emails_scanned"]
    run.candidate_emails = summary["candidate_emails"]
    run.status = InvoiceScanRun.Status.COMPLETED
    run.finished_at = timezone.now()
    run.details = {
        "since": since.isoformat() if since else None,
        "summary": summary,
        "emails": [
            candidate.as_dict()
            for candidate in evaluation["candidates"][:MAX_RECORDED_EMAILS]
        ],
    }
    run.save(
        update_fields=[
            "emails_scanned",
            "candidate_emails",
            "status",
            "finished_at",
            "details",
        ]
    )

    # The watermark deliberately stays put. Recognition lands in M3, so
    # advancing it now would mark these emails as handled and permanently
    # skip the invoices inside them.
    return run


def start_scan(
    user,
    trigger=InvoiceScanRun.Trigger.MANUAL,
    lookback_days=None,
    email_uuids=None,
) -> InvoiceScanRun:
    """Create the run row and queue the work, returning immediately."""
    run = InvoiceScanRun.objects.create(user=user, trigger=trigger)

    def _enqueue():
        from expense.tasks.scan import scan_user_invoices

        try:
            scan_user_invoices.delay(
                str(run.uuid),
                lookback_days=lookback_days,
                email_uuids=email_uuids,
            )
        except Exception:
            logger.exception(
                "Failed to queue expense scan %s; run stays pending", run.uuid
            )

    transaction.on_commit(_enqueue)
    return run

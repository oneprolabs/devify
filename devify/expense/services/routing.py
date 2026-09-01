"""
Whether an arriving email should be read as invoices instead of a thread.

An invoice notification is a document delivery, not a conversation.
Summarizing it produces something nobody reads, so the workflow sends it
down the invoice path instead - one pass, one charge.

Getting this wrong costs a real conversation its summary, so the rule here
is deliberately stricter than the one the manual scan uses.
"""

from __future__ import annotations

import logging

from expense.services.candidate_filter import evaluate_email, resolve_keywords
from expense.services.config_service import get_app_config, get_user_config

logger = logging.getLogger(__name__)


def keyword_is_deliberate(email, attachments, keywords) -> bool:
    """
    Require the keyword where a sender puts it on purpose.

    The scan filter also searches the body, which is right when a person
    has asked for a scan but far too loose to decide routing on its own:
    across a real mailbox it matched every phone bill and usage report
    that mentioned 发票 once in a footer. The subject and the filenames are
    where a sender says what an email is.
    """
    subject = (email.subject or "").lower()
    names = " ".join(
        (item.filename or item.safe_filename or "") for item in attachments
    ).lower()
    return any(word in subject or word in names for word in keywords)


def should_route_to_invoices(email, attachments=None) -> bool:
    """
    Decide without spending anything: no model call, no credit, no writes.

    A false positive is survivable - extraction finds nothing, and the
    workflow falls back to normal processing on the same charge - but it
    costs a wasted read, so the rule stays tight.
    """
    user_config = get_user_config(email.user)
    if not user_config.enabled:
        return False

    if attachments is None:
        attachments = list(email.attachments.all())

    keywords = resolve_keywords(user_config)
    if not keyword_is_deliberate(email, attachments, keywords):
        return False

    verdict = evaluate_email(
        email, attachments, get_app_config(), user_config, keywords=keywords
    )
    return verdict.is_candidate

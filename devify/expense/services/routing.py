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


def says_invoice(subject: str, filenames, keywords) -> bool:
    """
    Require the keyword where a sender puts it on purpose.

    The scan filter also searches the body, which is right when a person
    has asked for a scan but far too loose to decide on its own: across a
    real mailbox it matched every phone bill and usage report that
    mentioned 发票 once in a footer. The subject and the filenames are
    where a sender says what an email is.

    Takes plain strings so the fetch path, which has only a parsed message
    and no database rows yet, applies exactly the same rule.
    """
    haystack = " ".join(
        [subject or ""] + [name or "" for name in filenames]
    ).lower()
    return any(word in haystack for word in keywords)


def keyword_is_deliberate(email, attachments, keywords) -> bool:
    return says_invoice(
        email.subject or "",
        [
            (item.filename or item.safe_filename or "")
            for item in attachments
        ],
        keywords,
    )


def subject_terms(user) -> list[str]:
    """
    The keywords worth handing to an IMAP SUBJECT search.

    IMAP matches substrings, so a keyword that contains another one can
    never add a result: 电子发票 is already covered by 发票, and every extra
    term deepens the nested OR the server has to parse.
    """
    keywords = sorted(resolve_keywords(get_user_config(user)), key=len)
    kept: list[str] = []
    for word in keywords:
        if not any(shorter in word for shorter in kept):
            kept.append(word)
    return kept


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

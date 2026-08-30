"""
Category resolution and the memory behind it.

Three signals decide a category, and they are consulted cheapest-first so
the model is only asked about documents that are genuinely ambiguous:

1. a rule the user taught us by correcting an earlier invoice
2. the ticket type, when it settles the question by definition
3. what the model proposed

A user correction outranks the ticket-type mapping on purpose. The mapping
is a sensible default; a correction is this user telling us they disagree,
and a default that keeps overwriting an explicit choice reads as a bug.
"""

from __future__ import annotations

import logging

from django.db.models import F

from expense.constants import INVOICE_TYPE_CATEGORY_MAP, ExpenseCategory
from expense.models import CategoryRule, Invoice

logger = logging.getLogger(__name__)

VALID_CATEGORIES = {value for value, _ in ExpenseCategory.CHOICES}


def find_user_rule(user, seller_name="", seller_tax_id="", invoice_type=""):
    """
    Look for a remembered correction, most specific key first.

    A tax number identifies a company exactly; a name can be written
    several ways; a ticket type is the broadest of the three.
    """
    candidates = [
        (CategoryRule.MatchType.SELLER_TAX_ID, (seller_tax_id or "").strip()),
        (CategoryRule.MatchType.SELLER_NAME, (seller_name or "").strip()),
        (CategoryRule.MatchType.INVOICE_TYPE, (invoice_type or "").strip()),
    ]

    for match_type, value in candidates:
        if not value:
            continue
        rule = CategoryRule.objects.filter(
            user=user, match_type=match_type, match_value=value
        ).first()
        if rule:
            return rule

    return None


def classify(user, fields: dict) -> dict:
    """
    Settle the category for one extraction result.

    Mutates and returns ``fields`` with ``category`` and
    ``category_source`` filled in.
    """
    invoice_type = fields.get("invoice_type") or ""

    rule = find_user_rule(
        user,
        seller_name=fields.get("seller_name", ""),
        seller_tax_id=fields.get("seller_tax_id", ""),
        invoice_type=invoice_type,
    )
    if rule:
        CategoryRule.objects.filter(pk=rule.pk).update(
            hit_count=F("hit_count") + 1
        )
        fields["category"] = rule.category
        fields["category_source"] = Invoice.CategorySource.USER_RULE
        return fields

    mapped = INVOICE_TYPE_CATEGORY_MAP.get(invoice_type)
    if mapped:
        fields["category"] = mapped
        fields["category_source"] = Invoice.CategorySource.RULE
        return fields

    proposed = fields.get("category") or ""
    if proposed in VALID_CATEGORIES:
        fields["category_source"] = Invoice.CategorySource.MODEL
    else:
        fields["category"] = ExpenseCategory.OTHER
        fields["category_source"] = Invoice.CategorySource.MODEL

    return fields


def remember_correction(user, invoice: Invoice, category: str):
    """
    Turn a user's correction into a rule for next time.

    Keyed on the most specific identifier the invoice carries, so the
    lesson generalizes to that supplier rather than that one document.
    """
    if category not in VALID_CATEGORIES:
        return None

    if (invoice.seller_tax_id or "").strip():
        match_type = CategoryRule.MatchType.SELLER_TAX_ID
        match_value = invoice.seller_tax_id.strip()
    elif (invoice.seller_name or "").strip():
        match_type = CategoryRule.MatchType.SELLER_NAME
        match_value = invoice.seller_name.strip()
    elif (invoice.invoice_type or "").strip():
        match_type = CategoryRule.MatchType.INVOICE_TYPE
        match_value = invoice.invoice_type.strip()
    else:
        # Nothing stable to key on; the correction applies to this row only.
        return None

    rule, created = CategoryRule.objects.update_or_create(
        user=user,
        match_type=match_type,
        match_value=match_value[:255],
        defaults={
            "category": category,
            "created_from": CategoryRule.CreatedFrom.USER_CORRECTION,
        },
    )
    logger.info(
        "Category rule %s for %s=%s -> %s",
        "created" if created else "updated",
        match_type,
        match_value,
        category,
    )
    return rule

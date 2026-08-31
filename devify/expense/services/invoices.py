"""
Where an invoice is headed, and how many are at each stage.

An invoice is either waiting to be claimed, sitting in a live group, or
filed away because it will never be claimed. The third case is what keeps
a personal receipt from nagging forever in the unclaimed list.
"""

from __future__ import annotations

import logging

from django.db.models import Exists, OuterRef
from django.utils import timezone

from expense.models import ExpenseGroup, ExpenseGroupItem, Invoice

logger = logging.getLogger(__name__)

# A group in one of these states still holds its invoices.
LIVE_GROUP_STATES = (
    ExpenseGroup.Status.DRAFT,
    ExpenseGroup.Status.SUBMITTED,
)

# A reimbursed group is finished but keeps its invoices for the record.
SETTLED_GROUP_STATES = (ExpenseGroup.Status.REIMBURSED,)

FILED_REASONS = ("personal", "rejected", "expired", "other")


def claimed_subquery(states):
    return ExpenseGroupItem.objects.filter(
        invoice=OuterRef("pk"), group__status__in=states
    )


def annotate_stage(queryset):
    """Tag each row with whether it sits in a live or settled group."""
    return queryset.annotate(
        in_live_group=Exists(claimed_subquery(LIVE_GROUP_STATES)),
        in_settled_group=Exists(claimed_subquery(SETTLED_GROUP_STATES)),
    )


def by_stage(queryset, stage: str):
    """
    Narrow to one stage of the lifecycle.

    The stages are mutually exclusive by construction, so the counts add up
    to the total and a row never appears under two chips.
    """
    queryset = annotate_stage(queryset)

    if stage == "todo":
        return queryset.filter(
            disposition=Invoice.Disposition.TO_CLAIM,
            in_live_group=False,
            in_settled_group=False,
        )
    if stage == "claiming":
        return queryset.filter(in_live_group=True)
    if stage == "reimbursed":
        return queryset.filter(in_live_group=False, in_settled_group=True)
    if stage == "filed":
        return queryset.filter(
            disposition=Invoice.Disposition.FILED,
            in_live_group=False,
            in_settled_group=False,
        )
    return queryset


def stage_counts(user) -> dict:
    """One count per chip, plus the total."""
    base = Invoice.objects.filter(
        user=user,
        status__in=[Invoice.Status.EXTRACTED, Invoice.Status.DUPLICATE],
    )
    counts = {
        stage: by_stage(base, stage).count()
        for stage in ("todo", "claiming", "reimbursed", "filed")
    }
    counts["all"] = base.count()
    return counts


def file_invoices(user, uuids, reason: str = "") -> int:
    """
    Set invoices aside as never-to-be-claimed.

    An invoice already sitting in a group is left alone: it is spoken for,
    and filing it would quietly contradict a claim in progress.
    """
    reason = reason if reason in FILED_REASONS else "other"
    claimable = annotate_stage(
        Invoice.objects.filter(user=user, uuid__in=uuids)
    ).filter(in_live_group=False, in_settled_group=False)

    return claimable.update(
        disposition=Invoice.Disposition.FILED,
        filed_reason=reason,
        filed_at=timezone.now(),
    )


def unfile_invoices(user, uuids) -> int:
    """Put filed invoices back in the queue."""
    return Invoice.objects.filter(
        user=user,
        uuid__in=uuids,
        disposition=Invoice.Disposition.FILED,
    ).update(
        disposition=Invoice.Disposition.TO_CLAIM,
        filed_reason="",
        filed_at=None,
    )


def buyer_titles(user) -> list[dict]:
    """
    The billing titles this user's invoices actually carry.

    Derived rather than configured: it always reflects reality, and a title
    with a tax number is a company while one without is a person.
    """
    rows = (
        Invoice.objects.filter(user=user)
        .exclude(buyer_name="")
        .values_list("buyer_name", "buyer_tax_id")
    )
    seen: dict[str, dict] = {}
    for name, tax_id in rows:
        entry = seen.setdefault(
            name, {"name": name, "tax_id": tax_id or "", "count": 0}
        )
        entry["count"] += 1
        if tax_id and not entry["tax_id"]:
            entry["tax_id"] = tax_id
    for entry in seen.values():
        entry["kind"] = (
            "company" if entry["tax_id"] else "personal"
        )
    return sorted(seen.values(), key=lambda e: -e["count"])

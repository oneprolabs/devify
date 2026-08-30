"""
Reimbursement groups: membership, totals and the text people paste.

The summary exists because filing a claim means retyping the same figures
into a company form. Getting them out of here correctly is the point of
the whole application.
"""

from __future__ import annotations

import logging
from decimal import Decimal

from django.db import transaction
from django.utils.translation import gettext as _

from expense.constants import CATEGORY_LABELS_CN, ExpenseCategory
from expense.models import ExpenseGroup, ExpenseGroupItem, Invoice
from expense.services.money import to_chinese_amount

logger = logging.getLogger(__name__)

# A group in one of these states is settled; its invoices are spoken for.
ACTIVE_GROUP_STATES = (
    ExpenseGroup.Status.DRAFT,
    ExpenseGroup.Status.SUBMITTED,
    ExpenseGroup.Status.REIMBURSED,
)

# The summary is Chinese throughout and is meant to be pasted into a
# Chinese claim form, so its labels do not follow the UI language.
CATEGORY_LABELS = CATEGORY_LABELS_CN


class GroupError(Exception):
    """A membership change that would produce a wrong claim."""


def claimable_invoices(user, uuids):
    """Resolve invoice uuids, rejecting anything that cannot be claimed."""
    invoices = list(
        Invoice.objects.filter(user=user, uuid__in=uuids)
    )
    found = {str(invoice.uuid) for invoice in invoices}
    missing = [str(item) for item in uuids if str(item) not in found]
    if missing:
        raise GroupError(
            _("Unknown invoices: %(items)s") % {"items": ", ".join(missing)}
        )

    unusable = [
        invoice
        for invoice in invoices
        if invoice.status != Invoice.Status.EXTRACTED
    ]
    if unusable:
        raise GroupError(
            _("Only recognized invoices can be claimed; %(count)d cannot.")
            % {"count": len(unusable)}
        )

    return invoices


def assert_not_double_claimed(group, invoices):
    """
    Refuse an invoice that is already in another live group.

    Claiming the same expense twice is the one mistake this feature must
    never help a user make, so it is blocked rather than warned about.
    """
    clashes = (
        ExpenseGroupItem.objects.filter(
            invoice__in=invoices,
            group__status__in=ACTIVE_GROUP_STATES,
        )
        .exclude(group=group)
        .select_related("group", "invoice")
    )
    if clashes.exists():
        names = sorted({item.group.name for item in clashes})
        raise GroupError(
            _("Already claimed in: %(groups)s") % {"groups": ", ".join(names)}
        )


@transaction.atomic
def add_invoices(group: ExpenseGroup, uuids) -> int:
    invoices = claimable_invoices(group.user, uuids)
    assert_not_double_claimed(group, invoices)

    existing = set(
        ExpenseGroupItem.objects.filter(group=group).values_list(
            "invoice_id", flat=True
        )
    )
    order = ExpenseGroupItem.objects.filter(group=group).count()

    added = 0
    for invoice in invoices:
        if invoice.id in existing:
            continue
        ExpenseGroupItem.objects.create(
            group=group, invoice=invoice, sort_order=order
        )
        order += 1
        added += 1

    recalculate(group)
    return added


@transaction.atomic
def remove_invoices(group: ExpenseGroup, uuids) -> int:
    removed, _details = ExpenseGroupItem.objects.filter(
        group=group, invoice__uuid__in=uuids
    ).delete()
    recalculate(group)
    return removed


def recalculate(group: ExpenseGroup) -> ExpenseGroup:
    """Refresh the cached totals and the period the group covers."""
    invoices = [
        item.invoice
        for item in ExpenseGroupItem.objects.filter(
            group=group
        ).select_related("invoice")
    ]

    group.invoice_count = len(invoices)
    group.total_amount = sum(
        (invoice.total_amount or Decimal("0") for invoice in invoices),
        Decimal("0"),
    )
    group.tax_amount = sum(
        (invoice.tax_amount or Decimal("0") for invoice in invoices),
        Decimal("0"),
    )

    dates = [invoice.issue_date for invoice in invoices if invoice.issue_date]
    group.period_start = min(dates) if dates else None
    group.period_end = max(dates) if dates else None

    group.save(
        update_fields=[
            "invoice_count",
            "total_amount",
            "tax_amount",
            "period_start",
            "period_end",
            "updated_at",
        ]
    )
    return group


def category_breakdown(invoices) -> list[dict]:
    totals: dict[str, Decimal] = {}
    counts: dict[str, int] = {}
    for invoice in invoices:
        key = invoice.category or ExpenseCategory.OTHER
        totals[key] = totals.get(key, Decimal("0")) + (
            invoice.total_amount or Decimal("0")
        )
        counts[key] = counts.get(key, 0) + 1

    return [
        {
            "category": key,
            "label": CATEGORY_LABELS.get(key, key),
            "count": counts[key],
            "amount": str(amount),
        }
        for key, amount in sorted(
            totals.items(), key=lambda pair: pair[1], reverse=True
        )
    ]


def build_summary(group: ExpenseGroup) -> dict:
    """
    Everything needed to fill in a claim form, structured and as text.

    The text block is what most people actually use: one copy, one paste.
    """
    invoices = [
        item.invoice
        for item in ExpenseGroupItem.objects.filter(group=group)
        .select_related("invoice")
        .order_by("sort_order", "id")
    ]

    total = group.total_amount or Decimal("0")
    breakdown = category_breakdown(invoices)
    numbers = [
        invoice.invoice_no for invoice in invoices if invoice.invoice_no
    ]

    fields = {
        "name": group.name,
        "purpose": group.purpose,
        "trip_type": group.trip_type,
        "period_start": (
            group.period_start.isoformat() if group.period_start else ""
        ),
        "period_end": group.period_end.isoformat() if group.period_end else "",
        "invoice_count": group.invoice_count,
        "total_amount": str(total),
        "total_amount_cn": to_chinese_amount(total),
        "tax_amount": str(group.tax_amount or Decimal("0")),
        "currency": "CNY",
        "category_breakdown": breakdown,
        "invoice_numbers": numbers,
    }
    fields["text_block"] = render_text_block(fields)
    return fields


def render_text_block(fields: dict) -> str:
    """One pasteable block, in the order a claim form asks for it."""
    period = (
        f"{fields['period_start']} ~ {fields['period_end']}"
        if fields["period_start"]
        else ""
    )
    lines = [
        f"报销事由：{fields['purpose'] or fields['name']}",
    ]
    if period:
        lines.append(f"费用区间：{period}")
    lines.extend(
        [
            f"票据张数：{fields['invoice_count']}",
            f"价税合计：{fields['total_amount']} 元",
            f"金额大写：{fields['total_amount_cn']}",
            f"税额合计：{fields['tax_amount']} 元",
        ]
    )

    if fields["category_breakdown"]:
        lines.append("分类小计：")
        lines.extend(
            f"  {row['label']}：{row['amount']} 元（{row['count']} 张）"
            for row in fields["category_breakdown"]
        )

    if fields["invoice_numbers"]:
        lines.append("发票号码：")
        lines.extend(f"  {number}" for number in fields["invoice_numbers"])

    return "\n".join(lines)

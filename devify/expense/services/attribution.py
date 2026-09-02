"""
Which emails Expense took over, and what it produced from them.

The list and the detail view have to agree, and both have to agree with
what the user sees in Expense itself, so the rules live here rather than
being restated at each call site.

Two different questions, deliberately answered differently:

``invoice_count`` is what a badge shows, so it counts real invoices only.
One email routinely carries the same expense as PDF, OFD, XML and an
itinerary; those copies are absorbed into the invoice that carries the
number, and counting them would tell someone they have twelve invoices
where they have three.

``handled`` is whether Expense took the email at all, which stays true for
a re-forwarded invoice that produced only duplicates. It excludes the
placeholder rows written when the user was out of credits: Expense refused
that email rather than handling it, and those are exactly the ones someone
needs to find again after topping up.

Both follow a merge. The scanner reads merged-away emails and links the
invoices to the child, while the list only shows canonical parents, so a
count that ignored ``merged_children`` would lose them entirely.
"""

from __future__ import annotations

from django.db.models import Count, IntegerField, OuterRef, Q, Subquery, Value
from django.db.models.functions import Coalesce


def _rows_for(email_pk_ref, statuses=None, exclude_statuses=None):
    from expense.models import Invoice

    rows = Invoice.objects.filter(
        Q(email_message_id=email_pk_ref)
        | Q(email_message__merged_into_id=email_pk_ref)
    )
    if statuses is not None:
        rows = rows.filter(status__in=statuses)
    if exclude_statuses is not None:
        rows = rows.exclude(status__in=exclude_statuses)
    return rows


def _count_subquery(statuses=None, exclude_statuses=None):
    """
    A per-row count that does not join the outer query.

    A plain ``Count`` over two multi-valued paths would multiply the rows
    against each other; a subquery also keeps the list's own index usable,
    since the outer query needs no GROUP BY.
    """
    rows = (
        _rows_for(OuterRef("pk"), statuses, exclude_statuses)
        .order_by()
        .values(group=Value(1))
        .annotate(n=Count("*"))
        .values("n")
    )
    return Coalesce(
        Subquery(rows[:1], output_field=IntegerField()),
        Value(0),
        output_field=IntegerField(),
    )


def extracted_count_subquery():
    """Real invoices, for the badge."""
    from expense.models import Invoice

    return _count_subquery(statuses=[Invoice.Status.EXTRACTED])


def handled_count_subquery():
    """Anything Expense actually took on, for the filter."""
    from expense.models import Invoice

    return _count_subquery(
        exclude_statuses=[Invoice.Status.INSUFFICIENT_CREDITS]
    )


def extracted_count(email) -> int:
    """
    The same number as the annotation, for a caller without one.

    A detail view answering differently from the row the user clicked is
    the bug this exists to prevent.
    """
    from expense.models import Invoice

    return _rows_for(email.pk, statuses=[Invoice.Status.EXTRACTED]).count()

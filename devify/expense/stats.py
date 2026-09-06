"""
The numbers the app centre draws on the Expense card.
"""

from django.db.models import Sum

from .models import ExpenseGroup, Invoice


def expense_stats(user) -> dict:
    """
    Invoices read, what is not yet in a group, and open reimbursements.

    "Unfiled" is the number worth acting on: an extracted invoice that
    belongs to no group is one nobody has claimed yet.
    """
    extracted = Invoice.objects.filter(
        user=user, status=Invoice.Status.EXTRACTED
    )
    total_amount = extracted.aggregate(total=Sum("total_amount"))["total"]

    return {
        "invoices": extracted.count(),
        "unfiled": extracted.filter(group_items__isnull=True).count(),
        "open_groups": ExpenseGroup.objects.filter(
            user=user, status=ExpenseGroup.Status.DRAFT
        ).count(),
        "amount": float(total_amount or 0),
    }

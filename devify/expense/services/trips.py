"""
Group invoices into business trips, using only what recognition already
extracted.

This is pure rule work on dates and cities. No model is called and no
credit is spent, so the suggestions cost nothing to produce and a user can
see exactly why a receipt was grouped the way it was. That legibility
matters more than accuracy here: a claim has to be defensible.
"""

from __future__ import annotations

import logging
from collections import Counter
from datetime import timedelta
from decimal import Decimal

from django.utils import timezone

from expense.constants import ExpenseCategory
from expense.models import ExpenseGroup, Invoice, TripSuggestion

logger = logging.getLogger(__name__)

# How far back to look when inferring where someone normally works.
HOME_CITY_WINDOW_DAYS = 90

# A trip with no return leg is closed this long after its last receipt.
OPEN_TRIP_TAIL_DAYS = 1

# Trips shorter than this are same-day travel, not a trip worth grouping.
MIN_TRIP_INVOICES = 2


def infer_home_city(user, explicit: str = "") -> str:
    """
    Where this person normally spends.

    An explicit setting always wins; otherwise the most frequent city in
    the recent past is the best available signal.
    """
    if explicit:
        return explicit

    since = timezone.now().date() - timedelta(days=HOME_CITY_WINDOW_DAYS)
    cities = (
        Invoice.objects.filter(
            user=user,
            status=Invoice.Status.EXTRACTED,
            expense_date__gte=since,
        )
        .exclude(city="")
        .values_list("city", flat=True)
    )
    counts = Counter(cities)
    if not counts:
        return ""
    return counts.most_common(1)[0][0]


def claimable(user):
    """Invoices eligible for grouping, oldest first."""
    return list(
        Invoice.objects.filter(
            user=user,
            status=Invoice.Status.EXTRACTED,
            expense_date__isnull=False,
        )
        .exclude(group_items__isnull=False)
        .order_by("expense_date", "id")
    )


def detect_trips(user, home_city: str = "") -> list[dict]:
    """
    Find trips by using long-distance travel as the skeleton.

    A ticket leaving the home city opens a window; the first ticket back
    closes it. Everything spent elsewhere in between belongs to the trip.
    """
    home = infer_home_city(user, home_city)
    if not home:
        # Without a home city there is no "away", so there is nothing to
        # infer. Saying so beats inventing trips from noise.
        return []

    invoices = claimable(user)
    long_haul = [
        invoice
        for invoice in invoices
        if invoice.category == ExpenseCategory.TRANSPORT_LONG
    ]
    if not long_haul:
        return []

    trips: list[dict] = []
    open_trip = None

    for invoice in long_haul:
        going_out = bool(invoice.city) and invoice.city != home
        coming_back = invoice.city == home

        if open_trip is None:
            if going_out:
                open_trip = {
                    "destination_city": invoice.city,
                    "start_date": invoice.expense_date,
                    "end_date": invoice.expense_date,
                    "has_return": False,
                }
            continue

        if coming_back:
            open_trip["end_date"] = invoice.expense_date
            open_trip["has_return"] = True
            trips.append(open_trip)
            open_trip = None
        elif going_out:
            open_trip["end_date"] = invoice.expense_date

    if open_trip is not None:
        trips.append(open_trip)

    return [_fill_trip(trip, invoices, home) for trip in trips]


def _fill_trip(trip: dict, invoices, home: str) -> dict:
    """Pull every away-from-home receipt inside the window into the trip."""
    start = trip["start_date"]
    end = trip["end_date"]
    if not trip["has_return"]:
        end = end + timedelta(days=OPEN_TRIP_TAIL_DAYS)

    members = [
        invoice
        for invoice in invoices
        if invoice.expense_date
        and start <= invoice.expense_date <= end
        and (
            invoice.city != home
            # The journey home is a trip cost too. Its destination is the
            # home city, so filtering on location alone would drop the
            # return leg and understate the claim.
            or invoice.category == ExpenseCategory.TRANSPORT_LONG
        )
    ]

    total = sum(
        (invoice.total_amount or Decimal("0") for invoice in members),
        Decimal("0"),
    )

    # A complete return trip with somewhere to sleep is about as certain as
    # this gets; an open-ended one is a guess worth showing but not more.
    confidence = 0.9 if trip["has_return"] else 0.6
    if any(
        invoice.category == ExpenseCategory.ACCOMMODATION
        for invoice in members
    ):
        confidence = min(1.0, confidence + 0.05)

    trip.update(
        {
            "end_date": end,
            "invoices": members,
            "invoice_ids": [str(invoice.uuid) for invoice in members],
            "total_amount": total,
            "confidence": confidence,
        }
    )
    return trip


def refresh_suggestions(user, home_city: str = "") -> int:
    """Recompute suggestions, leaving the user's own decisions alone."""
    trips = [
        trip
        for trip in detect_trips(user, home_city)
        if len(trip["invoices"]) >= MIN_TRIP_INVOICES
    ]

    # Only untouched suggestions are replaced; accepted and dismissed ones
    # are decisions, not stale computation.
    TripSuggestion.objects.filter(
        user=user, status=TripSuggestion.Status.SUGGESTED
    ).delete()

    created = 0
    for trip in trips:
        already_decided = TripSuggestion.objects.filter(
            user=user,
            destination_city=trip["destination_city"],
            start_date=trip["start_date"],
        ).exclude(status=TripSuggestion.Status.SUGGESTED)
        if already_decided.exists():
            continue

        TripSuggestion.objects.create(
            user=user,
            destination_city=trip["destination_city"],
            start_date=trip["start_date"],
            end_date=trip["end_date"],
            invoice_ids=trip["invoice_ids"],
            total_amount=trip["total_amount"],
            confidence=trip["confidence"],
        )
        created += 1

    return created


def accept(suggestion: TripSuggestion, name: str = "") -> ExpenseGroup:
    """Turn a suggestion into a real group the user can file."""
    from expense.services.groups import add_invoices

    label = name or (
        f"{suggestion.start_date:%Y-%m-%d} {suggestion.destination_city}"
    )

    group_name = label
    for index in range(2, 100):
        if not ExpenseGroup.objects.filter(
            user=suggestion.user, name=group_name
        ).exists():
            break
        group_name = f"{label} ({index})"

    group = ExpenseGroup.objects.create(
        user=suggestion.user,
        name=group_name,
        purpose=label,
        trip_type=ExpenseGroup.TripType.BUSINESS_TRIP,
    )
    add_invoices(group, suggestion.invoice_ids)

    suggestion.status = TripSuggestion.Status.ACCEPTED
    suggestion.accepted_group = group
    suggestion.save(update_fields=["status", "accepted_group", "updated_at"])
    return group

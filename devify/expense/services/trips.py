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
from datetime import timedelta
from decimal import Decimal

from expense.constants import ExpenseCategory
from expense.models import ExpenseGroup, Invoice, TripSuggestion

logger = logging.getLogger(__name__)


# A trip with no return leg is closed this long after its last receipt.
OPEN_TRIP_TAIL_DAYS = 1

# Trips shorter than this are same-day travel, not a trip worth grouping.
MIN_TRIP_INVOICES = 2


# Chinese city names arrive with the administrative suffix attached or not,
# depending on the document: a train ticket says "北京", a taxi receipt says
# "北京市". Counted as written they are two places, which is how a home of
# 北京 (11 invoices) lost the vote to 上海 (8) and inverted every trip after
# it. Every comparison in this module goes through canonical_city.
# Prefix-free longest-first: 特别行政区 and 自治区 have to be tried before
# 区 would bite off only its last character. Bare 区 and 县 are deliberately
# absent — they name a district or county, not a city, and stripping them
# collides distinct places: 西安区 is part of 辽源 in Jilin, and reducing it
# to 西安 would let a Xi'an user's home city swallow the receipt. 自治州 and
# 地区 are absent for a different reason: they are part of the name, not a
# suffix on it — 巴音郭楞蒙古自治州 shortened to 巴音郭楞蒙古 is not a
# place, and it is what the trip and its expense group get named.
CITY_SUFFIXES = ("特别行政区", "自治区", "省", "市")


def canonical_city(city: str) -> str:
    """One spelling per city, so counting and comparing agree."""
    name = (city or "").strip()
    for suffix in CITY_SUFFIXES:
        # Only strip a suffix that leaves a name behind — "市" alone is not
        # a city. Trailing suffix only: the values in play are "北京" and
        # "北京市", not "北京市朝阳区", and guessing at a district-level
        # name would be a different job from normalising a spelling.
        if len(name) > len(suffix) + 1 and name.endswith(suffix):
            return name[: -len(suffix)]
    return name


def home_city_for(user, explicit: str = "") -> str:
    """
    The city this person travels out from, as they configured it.

    Deliberately not inferred. This used to fall back to the most frequent
    city of the last 90 days, which is a bad proxy for home and got it
    wrong in exactly the case the feature exists for: someone who travels
    spends more in the places they travel to, so the destination outvotes
    home. Getting it wrong does not degrade trip detection, it inverts it —
    every outbound ticket reads as coming home and every return as leaving,
    so two round trips come back as one trip straddling both plus an
    unclosed fragment. An empty answer produces no suggestions, which is
    the honest outcome until the user tells us.
    """
    return canonical_city(explicit)


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


def at_home(invoice, home: str) -> bool:
    """
    Whether this receipt was incurred in the user's own city.

    Two readings have to agree with "home", because the station list maps a
    station to its prefecture-level city: 义乌 is listed under 金华, 昆山南
    under 苏州. A user who lives in 义乌 and writes that as their home city
    would otherwise never come home — their return leg would read as another
    departure, leaving the trip open to swallow every journey after it.

    So a station whose name starts with the home city counts as home too.
    Station names are built from the city they serve, so 义乌 matches 义乌,
    昆山 matches 昆山南 and 北京 matches 北京南, while a user who writes the
    prefecture instead (苏州) is already matched by the looked-up city.
    """
    if canonical_city(invoice.city) == home:
        return True
    details = invoice.ticket_details or {}
    station = str(details.get("to_station") or "").strip()
    return bool(home) and station.startswith(home)


def detect_trips(user, home_city: str = "") -> list[dict]:
    """
    Find trips by using long-distance travel as the skeleton.

    A ticket leaving the home city opens a window; the first ticket back
    closes it. Everything spent elsewhere in between belongs to the trip.
    """
    home = home_city_for(user, home_city)
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
        city = canonical_city(invoice.city)
        coming_back = at_home(invoice, home)
        going_out = bool(city) and not coming_back

        if open_trip is None:
            if going_out:
                open_trip = {
                    # Canonical, not raw: this is the dedup key in
                    # refresh_suggestions, so a differently-spelled duplicate
                    # opening the same window would otherwise miss the
                    # already-decided lookup and resurrect a dismissed trip.
                    "destination_city": city,
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
            canonical_city(invoice.city) != home
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

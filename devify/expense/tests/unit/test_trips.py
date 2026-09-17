"""
Unit tests for trip detection.

These exist because trip detection had none, and a spelling difference in
one field silently inverted every trip it produced: a user with 16 Beijing
invoices spread across "北京" and "北京市" had a home city of 上海 inferred
from 11 Shanghai ones, so every outbound ticket read as coming home and
every return as leaving. The numbers below are that production case.
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from expense.models import Invoice
from expense.services.trips import canonical_city, detect_trips, home_city_for
from threadline.models import EmailMessage


class TestCanonicalCity:
    """The two spellings that actually occur have to agree."""

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("北京", "北京"),
            ("北京市", "北京"),
            ("上海市", "上海"),
            ("  上海  ", "上海"),
            ("香港特别行政区", "香港"),
            # 自治区 must be tried before 区 would bite off one character.
            ("西藏自治区", "西藏"),
            ("内蒙古自治区", "内蒙古"),
            ("", ""),
            (None, ""),
            # Not a city: nothing would be left behind.
            ("市", "市"),
            # A station is not a city and must not be mistaken for one.
            ("上海虹桥", "上海虹桥"),
            # A district is not a city either. 西安区 belongs to 辽源 in
            # Jilin; reducing it to 西安 would let a Xi'an user's home city
            # swallow the receipt and drop it from their trip.
            ("西安区", "西安区"),
            ("朝阳区", "朝阳区"),
        ],
    )
    def test_spelling_collapses(self, raw, expected):
        assert canonical_city(raw) == expected


def _invoice(user, day, city, category="transport_long", amount="661.00",
             _n=[0], **kw):
    """Invoices hang off an email; trip detection never reads it."""
    _n[0] += 1
    email = EmailMessage.objects.create(
        user=user,
        message_id=f"trip-test-{_n[0]:04d}",
        subject="发票",
        sender="billing@example.com",
        recipients="user@example.com",
        received_at=timezone.now() - timedelta(days=1),
    )
    return Invoice.objects.create(
        user=user,
        email_message=email,
        status=Invoice.Status.EXTRACTED,
        expense_date=date(2026, 9, day),
        city=city,
        category=category,
        total_amount=Decimal(amount),
        **kw,
    )


@pytest.mark.django_db
class TestHomeCity:
    def test_the_configured_spelling_is_normalised(self, user):
        """
        "北京" and "北京市" have to compare equal, or a user who typed one
        while their documents say the other gets no trips at all.
        """
        assert home_city_for(user, "北京市") == "北京"
        assert home_city_for(user, "  上海  ") == "上海"

    def test_nothing_configured_means_nothing_assumed(self, user):
        for i in range(11):
            _invoice(user, 1 + (i % 28), "上海", category="meals", amount="10")

        assert home_city_for(user) == ""


@pytest.mark.django_db
class TestDetectTrips:
    def test_two_round_trips_stay_whole(self, user):
        """
        The production case: two Beijing→Shanghai round trips. Each outbound
        must open a trip and the matching return must close it — one trip
        per journey, not one trip straddling both.
        """
        _invoice(user, 9, "上海")   # out
        _invoice(user, 10, "北京")  # back
        _invoice(user, 14, "上海")  # out
        _invoice(user, 16, "北京")  # back

        trips = detect_trips(user, "北京市")

        assert len(trips) == 2
        assert [t["destination_city"] for t in trips] == ["上海", "上海"]
        assert trips[0]["start_date"] == date(2026, 9, 9)
        assert trips[0]["end_date"] == date(2026, 9, 10)
        assert trips[1]["start_date"] == date(2026, 9, 14)
        assert trips[1]["end_date"] == date(2026, 9, 16)

    def test_return_leg_does_not_open_a_trip(self, user):
        """
        A return ticket's destination is home, so it closes a window. Reading
        it as an outbound — which is what the unnormalised compare did — is
        what produced trips named after the home city.
        """
        _invoice(user, 10, "北京")  # a return with nothing open

        assert detect_trips(user, "北京") == []

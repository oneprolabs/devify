"""Integration tests for inferring business trips from the timeline."""

from datetime import date
from decimal import Decimal

import pytest
from django.utils import timezone

from expense.constants import ExpenseCategory
from expense.models import ExpenseGroup, Invoice, TripSuggestion
from expense.services import trips as trip_service
from threadline.models import EmailMessage


pytestmark = [pytest.mark.integration, pytest.mark.django_db]

TRIPS_URL = "/api/v1/apps/expense/trips"


def make_invoice(user, city, day, category, counter=[0], **overrides):
    counter[0] += 1
    email = EmailMessage.objects.create(
        user=user,
        message_id=f"email_trip_{counter[0]:04d}",
        subject="发票",
        sender="billing@example.com",
        recipients="user@example.com",
        received_at=timezone.now(),
    )
    payload = {
        "user": user,
        "email_message": email,
        "status": Invoice.Status.EXTRACTED,
        "invoice_no": f"T{counter[0]:08d}",
        "issue_date": date(2026, 8, day),
        "seller_name": "某供应商",
        "total_amount": Decimal("100.00"),
        "category": category,
        "city": city,
    }
    payload.update(overrides)
    return Invoice.objects.create(**payload)


def seed_trip(user):
    """Beijing base, a return trip to Shanghai on the 12th to the 15th."""
    make_invoice(user, "北京", 1, ExpenseCategory.TRANSPORT_LOCAL)
    make_invoice(user, "北京", 5, ExpenseCategory.MEALS)
    make_invoice(user, "上海", 12, ExpenseCategory.TRANSPORT_LONG)
    make_invoice(user, "上海", 13, ExpenseCategory.ACCOMMODATION)
    make_invoice(user, "上海", 14, ExpenseCategory.MEALS)
    make_invoice(user, "北京", 15, ExpenseCategory.TRANSPORT_LONG)


class TestHomeCity:
    def test_the_most_frequent_city_wins(self, user):
        make_invoice(user, "北京", 1, ExpenseCategory.MEALS)
        make_invoice(user, "北京", 2, ExpenseCategory.MEALS)
        make_invoice(user, "上海", 3, ExpenseCategory.MEALS)

        assert trip_service.infer_home_city(user) == "北京"

    def test_an_explicit_setting_wins(self, user):
        make_invoice(user, "北京", 1, ExpenseCategory.MEALS)

        assert trip_service.infer_home_city(user, "深圳") == "深圳"

    def test_no_data_gives_no_city(self, user):
        assert trip_service.infer_home_city(user) == ""


class TestDetectTrips:
    def test_a_return_trip_is_found(self, user):
        seed_trip(user)

        trips = trip_service.detect_trips(user, "北京")

        assert len(trips) == 1
        assert trips[0]["destination_city"] == "上海"
        assert trips[0]["start_date"] == date(2026, 8, 12)
        assert trips[0]["end_date"] == date(2026, 8, 15)

    def test_away_spending_is_pulled_into_the_trip(self, user):
        seed_trip(user)

        trip = trip_service.detect_trips(user, "北京")[0]

        # The hotel and the meal in Shanghai belong to the trip; the
        # Beijing receipts do not.
        away = [
            invoice for invoice in trip["invoices"] if invoice.city != "北京"
        ]
        assert {invoice.city for invoice in away} == {"上海"}
        assert len(away) == 3

    def test_the_return_leg_is_part_of_the_trip(self, user):
        # Its destination is the home city, so filtering on location alone
        # would drop it and understate the claim.
        seed_trip(user)

        trip = trip_service.detect_trips(user, "北京")[0]

        long_haul = [
            invoice
            for invoice in trip["invoices"]
            if invoice.category == ExpenseCategory.TRANSPORT_LONG
        ]
        assert len(long_haul) == 2
        assert trip["total_amount"] == Decimal("400.00")

    def test_home_spending_stays_out(self, user):
        seed_trip(user)

        trip = trip_service.detect_trips(user, "北京")[0]

        # The Beijing meal on the 5th is outside the window and stays out;
        # only the return ticket carries the home city.
        assert all(
            invoice.city != "北京"
            or invoice.category == ExpenseCategory.TRANSPORT_LONG
            for invoice in trip["invoices"]
        )

    def test_a_complete_trip_is_more_certain_than_an_open_one(self, user):
        seed_trip(user)
        complete = trip_service.detect_trips(user, "北京")[0]

        Invoice.objects.filter(
            city="北京", category=ExpenseCategory.TRANSPORT_LONG
        ).delete()
        open_ended = trip_service.detect_trips(user, "北京")[0]

        assert complete["confidence"] > open_ended["confidence"]

    def test_no_long_distance_ticket_means_no_trip(self, user):
        make_invoice(user, "北京", 1, ExpenseCategory.MEALS)
        make_invoice(user, "上海", 2, ExpenseCategory.MEALS)

        assert trip_service.detect_trips(user, "北京") == []

    def test_without_a_home_city_nothing_is_inferred(self, user):
        # Inventing trips from noise would be worse than staying quiet.
        make_invoice(user, "", 1, ExpenseCategory.TRANSPORT_LONG)

        assert trip_service.detect_trips(user) == []

    def test_invoices_already_claimed_are_left_alone(self, user):
        seed_trip(user)
        group = ExpenseGroup.objects.create(user=user, name="已有报销")
        from expense.services.groups import add_invoices

        add_invoices(
            group,
            [
                str(uuid)
                for uuid in Invoice.objects.filter(city="上海").values_list(
                    "uuid", flat=True
                )
            ],
        )

        assert trip_service.detect_trips(user, "北京") == []


class TestSuggestions:
    def test_a_trip_becomes_a_suggestion(self, user):
        seed_trip(user)

        created = trip_service.refresh_suggestions(user, "北京")

        assert created == 1
        assert TripSuggestion.objects.count() == 1

    def test_refreshing_replaces_untouched_suggestions(self, user):
        seed_trip(user)
        trip_service.refresh_suggestions(user, "北京")

        trip_service.refresh_suggestions(user, "北京")

        assert TripSuggestion.objects.count() == 1

    def test_a_dismissed_suggestion_does_not_come_back(self, user):
        seed_trip(user)
        trip_service.refresh_suggestions(user, "北京")
        suggestion = TripSuggestion.objects.get()
        suggestion.status = TripSuggestion.Status.DISMISSED
        suggestion.save(update_fields=["status"])

        trip_service.refresh_suggestions(user, "北京")

        assert (
            TripSuggestion.objects.filter(
                status=TripSuggestion.Status.SUGGESTED
            ).count()
            == 0
        )

    def test_accepting_creates_a_group_with_the_invoices(self, user):
        seed_trip(user)
        trip_service.refresh_suggestions(user, "北京")
        suggestion = TripSuggestion.objects.get()

        group = trip_service.accept(suggestion)
        suggestion.refresh_from_db()

        assert group.trip_type == ExpenseGroup.TripType.BUSINESS_TRIP
        assert group.invoice_count == 4
        assert suggestion.status == TripSuggestion.Status.ACCEPTED
        assert suggestion.accepted_group_id == group.id

    def test_the_group_is_named_after_the_trip(self, user):
        seed_trip(user)
        trip_service.refresh_suggestions(user, "北京")

        group = trip_service.accept(TripSuggestion.objects.get())

        assert "上海" in group.name
        assert "2026-08-12" in group.name


class TestTripAPI:
    def test_suggestions_can_be_recomputed_for_free(self, api_client, user):
        seed_trip(user)
        from expense.services.config_service import get_user_config

        config = get_user_config(user)
        config.home_city = "北京"
        config.save(update_fields=["home_city"])
        api_client.force_authenticate(user=user)

        response = api_client.post(TRIPS_URL)

        assert response.data["data"]["created"] == 1

    def test_accepting_through_the_api_returns_the_group(
        self, api_client, user
    ):
        seed_trip(user)
        trip_service.refresh_suggestions(user, "北京")
        suggestion = TripSuggestion.objects.get()
        api_client.force_authenticate(user=user)

        response = api_client.post(f"{TRIPS_URL}/{suggestion.uuid}/accept")

        assert response.status_code == 201
        assert response.data["data"]["invoice_count"] == 4

    def test_a_decided_suggestion_cannot_be_accepted_again(
        self, api_client, user
    ):
        seed_trip(user)
        trip_service.refresh_suggestions(user, "北京")
        suggestion = TripSuggestion.objects.get()
        trip_service.accept(suggestion)
        api_client.force_authenticate(user=user)

        response = api_client.post(f"{TRIPS_URL}/{suggestion.uuid}/accept")

        assert response.status_code == 400

    def test_a_suggestion_can_be_dismissed(self, api_client, user):
        seed_trip(user)
        trip_service.refresh_suggestions(user, "北京")
        suggestion = TripSuggestion.objects.get()
        api_client.force_authenticate(user=user)

        api_client.post(f"{TRIPS_URL}/{suggestion.uuid}/dismiss")
        suggestion.refresh_from_db()

        assert suggestion.status == TripSuggestion.Status.DISMISSED

    def test_another_users_suggestion_is_not_found(
        self, api_client, user, other_user
    ):
        seed_trip(other_user)
        trip_service.refresh_suggestions(other_user, "北京")
        suggestion = TripSuggestion.objects.get()
        api_client.force_authenticate(user=user)

        response = api_client.post(f"{TRIPS_URL}/{suggestion.uuid}/accept")

        assert response.status_code == 404

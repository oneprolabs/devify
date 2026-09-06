"""
Unit tests for the Relay header counts.
"""

from datetime import timedelta

import pytest
from django.utils import timezone

from relay.models import RelayDelivery, RelayEvent, RelaySubscription
from relay.stats import relay_stats
from threadline.models import EmailMessage


@pytest.fixture
def subscription(db, django_user_model):
    user = django_user_model.objects.create_user(
        username="relay-stats", password="x"
    )
    return RelaySubscription.objects.create(
        user=user,
        name="Product backlog",
        target_type=RelaySubscription.TargetType.JIRA,
        enabled=True,
        config={},
    )


def _delivery(subscription, status, **kwargs):
    message = EmailMessage.objects.create(
        user=subscription.user,
        message_id=f"relay-stats-{RelayEvent.objects.count()}@example.com",
        subject="Seed",
        sender="seed@example.com",
        recipients="me@example.com",
        received_at=timezone.now(),
    )
    event = RelayEvent.objects.create(
        user=subscription.user,
        email_message=message,
    )
    delivery = RelayDelivery.objects.create(
        event=event,
        subscription=subscription,
        target_type=subscription.target_type,
        status=status,
        idempotency_key=f"relay-stats-{event.pk}-{subscription.pk}",
    )
    if "created_at" in kwargs:
        RelayDelivery.objects.filter(pk=delivery.pk).update(
            created_at=kwargs["created_at"]
        )
    return delivery


@pytest.mark.django_db
@pytest.mark.unit
class TestRelayStats:
    def test_counts_channels_deliveries_and_failures(self, subscription):
        _delivery(subscription, RelayDelivery.Status.SUCCESS)
        _delivery(subscription, RelayDelivery.Status.SUCCESS)
        _delivery(subscription, RelayDelivery.Status.FAILED)

        stats = relay_stats(subscription.user)

        assert stats["channels"] == 1
        assert stats["total"] == 3
        assert stats["failed"] == 1
        assert stats["by_channel"] == {subscription.target_type: 3}

    def test_success_rate_ignores_rows_still_in_flight(self, subscription):
        _delivery(subscription, RelayDelivery.Status.SUCCESS)
        _delivery(subscription, RelayDelivery.Status.FAILED)
        _delivery(subscription, RelayDelivery.Status.PENDING)

        # One of two settled deliveries succeeded; the pending one is not
        # evidence either way.
        assert relay_stats(subscription.user)["success_rate"] == 50.0

    def test_no_deliveries_means_no_rate(self, subscription):
        assert relay_stats(subscription.user)["success_rate"] == 0.0

    def test_this_week_counts_only_the_last_seven_days(self, subscription):
        _delivery(subscription, RelayDelivery.Status.SUCCESS)
        _delivery(
            subscription,
            RelayDelivery.Status.SUCCESS,
            created_at=timezone.now() - timedelta(days=30),
        )

        assert relay_stats(subscription.user)["deliveries_this_week"] == 1

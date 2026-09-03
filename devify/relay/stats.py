"""
The numbers the app centre draws on the Relay card.

Kept beside the models rather than in the app centre, because Relay is the
only place that knows what "a channel" or "a failed delivery" means.
"""

from datetime import timedelta

from django.utils import timezone

from .models import RelayDelivery, RelaySubscription


def relay_stats(user) -> dict:
    """Enabled channels, deliveries in the last seven days, and failures."""
    week_ago = timezone.now() - timedelta(days=7)
    deliveries = RelayDelivery.objects.filter(subscription__user=user)

    return {
        "channels": RelaySubscription.objects.filter(
            user=user, enabled=True
        ).count(),
        "deliveries_this_week": deliveries.filter(
            created_at__gte=week_ago
        ).count(),
        "failed": deliveries.filter(
            status=RelayDelivery.Status.FAILED
        ).count(),
    }

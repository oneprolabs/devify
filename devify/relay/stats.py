"""
The numbers the app centre draws on the Relay card.

Kept beside the models rather than in the app centre, because Relay is the
only place that knows what "a channel" or "a failed delivery" means.
"""

from datetime import timedelta

from django.db.models import Count
from django.utils import timezone

from .models import RelayDelivery, RelaySubscription


def relay_stats(user) -> dict:
    """
    What the app-centre card and the Relay page header both count.

    The page needs the whole set; the card reads three of them.
    """
    week_ago = timezone.now() - timedelta(days=7)
    deliveries = RelayDelivery.objects.filter(subscription__user=user)

    total = deliveries.count()
    failed = deliveries.filter(status=RelayDelivery.Status.FAILED).count()
    succeeded = deliveries.filter(
        status=RelayDelivery.Status.SUCCESS
    ).count()

    # Pending and processing rows have not decided yet, so they count
    # against neither side of the rate.
    settled = succeeded + failed

    by_channel = (
        deliveries.values("target_type")
        .annotate(count=Count("id"))
        .order_by("-count")
    )

    return {
        "channels": RelaySubscription.objects.filter(
            user=user, enabled=True
        ).count(),
        "total": total,
        "deliveries_this_week": deliveries.filter(
            created_at__gte=week_ago
        ).count(),
        "failed": failed,
        "success_rate": (
            round(succeeded / settled * 100, 1) if settled else 0.0
        ),
        "by_channel": {
            row["target_type"]: row["count"] for row in by_channel
        },
    }

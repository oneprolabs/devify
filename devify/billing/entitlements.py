"""What the signed-in account may use, derived from its active subscription.

The desktop client polls ``GET /api/v1/me/entitlements`` after every sign-in
and caches the answer. The contract it expects is documented in
``docs/entitlements.md``.
"""

from __future__ import annotations

from typing import Any

from billing.services.subscription_service import SubscriptionService


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    items = []
    for item in value:
        text = str(item).strip()
        if text:
            items.append(text)
    return items


def _counter_map(value: Any) -> dict[str, int]:
    if not isinstance(value, dict):
        return {}
    counters = {}
    for key, item in value.items():
        if not isinstance(key, str) or not key.strip():
            continue
        try:
            counters[key.strip()] = int(item)
        except (TypeError, ValueError):
            continue
    return counters


def build_entitlements(user) -> dict:
    """Return the entitlements of ``user``'s active subscription.

    Plans carry their grants in ``Plan.metadata``:

    * ``features`` -- capability keys the plan includes, e.g.
      ``["ingest.upload", "bridge.agent_cli"]``;
    * ``limits`` / ``quotas`` -- numeric ceilings keyed by their client name,
      e.g. ``{"limits.ingest.conversations": 500}``;
    * ``fallback_features`` -- what survives a stale snapshot;
    * ``enforced`` -- opt in only once the plan lists its features, otherwise
      the client keeps its legacy "everything is allowed" behaviour.

    The ``internal`` flag is what gates features reserved for staff accounts,
    such as the local agent access kit. It is never inferred from ``is_staff``:
    a staff account still needs an active subscription to the internal plan.
    """

    subscription = SubscriptionService.get_active_subscription(user.pk)
    plan = subscription.plan if subscription is not None else None
    metadata = {}
    if plan is not None and isinstance(plan.metadata, dict):
        metadata = plan.metadata

    features = _string_list(metadata.get("features"))
    return {
        "plan": (
            {
                "slug": plan.slug,
                "name": plan.name,
                "status": subscription.status,
                "current_period_end": (
                    subscription.current_period_end.isoformat()
                    if subscription.current_period_end
                    else None
                ),
            }
            if plan is not None
            else None
        ),
        "features": features,
        "limits": _counter_map(metadata.get("limits")),
        "quotas": _counter_map(metadata.get("quotas")),
        "usage": {},
        "enforced": bool(metadata.get("enforced")) and bool(features),
        "fallback_features": _string_list(metadata.get("fallback_features")),
        "expires_at": None,
        "internal": bool(plan is not None and plan.is_internal),
    }

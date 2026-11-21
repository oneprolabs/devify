"""Baseline grants must preserve the plan's enforcement contract."""

from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from billing.entitlements import build_entitlements


@pytest.mark.parametrize(
    "metadata,expected",
    [
        ({"enforced": True}, False),
        ({"enforced": True, "features": []}, False),
        ({"enforced": True, "features": ["ingest.upload"]}, True),
        ({"enforced": False, "features": ["ingest.upload"]}, False),
        (
            {"enforced": True, "features": ["cloud.chat_summary"]},
            True,
        ),
    ],
)
def test_baseline_summary_does_not_enable_plan_enforcement(metadata, expected):
    original = deepcopy(metadata)
    user = SimpleNamespace(pk=1, is_authenticated=True, is_active=True)
    subscription = SimpleNamespace(
        plan=SimpleNamespace(
            slug="test", name="Test", metadata=metadata, is_internal=False
        ),
        status="active",
        current_period_end=None,
    )
    with patch(
        "billing.entitlements.SubscriptionService.get_active_subscription",
        return_value=subscription,
    ):
        result = build_entitlements(user)
    assert result["enforced"] is expected
    assert result["features"].count("cloud.chat_summary") == 1
    assert result["internal"] is False
    assert metadata == original

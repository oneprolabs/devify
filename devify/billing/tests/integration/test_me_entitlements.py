"""The signed-in account can read its subscription entitlements."""

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from billing.models import Subscription

URL = "/api/v1/me/entitlements"

pytestmark = pytest.mark.django_db


def _get(user):
    client = APIClient()
    client.force_authenticate(user)
    return client.get(URL)


def _data(user):
    """The renderer wraps every payload in ``{"code", "message", "data"}``."""
    return _get(user).json()["data"]


def test_anonymous_request_is_rejected():
    assert APIClient().get(URL).status_code in (401, 403)


def test_free_user_is_not_internal(test_user_with_free_subscription):
    response = _get(test_user_with_free_subscription)

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["plan"]["slug"] == "free"
    assert data["internal"] is False
    assert data["features"] == []
    assert data["enforced"] is False


def test_internal_plan_marks_the_account_internal(
    test_user_with_internal_subscription,
):
    data = _data(test_user_with_internal_subscription)

    assert data["plan"]["slug"] == "internal"
    assert data["plan"]["status"] == "active"
    assert data["plan"]["current_period_end"]
    assert data["internal"] is True


def test_staff_without_an_internal_plan_is_not_internal(
    test_user_with_free_subscription,
):
    user = test_user_with_free_subscription
    user.is_staff = True
    user.save(update_fields=["is_staff"])

    assert _data(user)["internal"] is False


def test_plan_metadata_is_exposed(
    test_user_with_internal_subscription, internal_plan
):
    internal_plan.metadata = {
        **internal_plan.metadata,
        "features": ["ai.local_agent", "bridge.agent_cli", "ingest.upload"],
        "limits": {"limits.ingest.conversations": 500, "broken": "many"},
        "quotas": {"quotas.cloud.ask_per_day": 100},
        "fallback_features": ["local.wechat_read"],
        "enforced": True,
    }
    internal_plan.save(update_fields=["metadata"])

    data = _data(test_user_with_internal_subscription)

    assert data["features"] == [
        "ai.local_agent",
        "bridge.agent_cli",
        "ingest.upload",
    ]
    assert data["limits"] == {"limits.ingest.conversations": 500}
    assert data["quotas"] == {"quotas.cloud.ask_per_day": 100}
    assert data["fallback_features"] == ["local.wechat_read"]
    assert data["enforced"] is True


def test_enforced_requires_a_feature_list(
    test_user_with_internal_subscription, internal_plan
):
    internal_plan.metadata = {**internal_plan.metadata, "enforced": True}
    internal_plan.save(update_fields=["metadata"])

    assert _data(test_user_with_internal_subscription)["enforced"] is False


def test_canceled_subscription_grants_nothing(
    test_user_with_internal_subscription,
):
    Subscription.objects.filter(
        user=test_user_with_internal_subscription, status="active"
    ).update(status="canceled", current_period_end=timezone.now())

    data = _data(test_user_with_internal_subscription)

    assert data["plan"] is None
    assert data["internal"] is False
    assert data["features"] == []

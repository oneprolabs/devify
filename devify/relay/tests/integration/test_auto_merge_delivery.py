"""Follow-up messages must update the original destination record."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from django.utils import timezone

from relay.models import RelayDelivery, RelayEvent, RelaySubscription
from relay.services.dispatcher import RelayDispatcher
from threadline.models import EmailMessage

pytestmark = pytest.mark.integration


@pytest.mark.django_db
@pytest.mark.parametrize("target_type", ["jira", "feishu_bitable"])
@pytest.mark.parametrize("new_anchor", [True, False])
@pytest.mark.parametrize("trigger_source", [None, "api_retry"])
def test_follow_up_updates_cluster_record_once(
    django_user_model, monkeypatch, target_type, new_anchor, trigger_source,
):
    user = django_user_model.objects.create_user("follow-up-delivery")
    original = EmailMessage.objects.create(
        user=user, message_id="original", received_at=timezone.now(),
    )
    follow_up = EmailMessage.objects.create(
        user=user, message_id="follow-up", received_at=timezone.now(),
    )
    source, anchor = (
        (original, follow_up) if new_anchor else (follow_up, original)
    )
    source.merged_into = anchor
    source.merge_reason = "text_similarity"
    source.save(update_fields=["merged_into", "merge_reason"])
    subscription = RelaySubscription.objects.create(
        user=user, name="follow-up", target_type=target_type,
        strategies={
            "auto_merge_strategy": "update",
            "manual_merge_strategy": "linked",
            "retry_issue_strategy": "update",
        },
    )
    prior = RelayEvent.objects.create(
        user=user, email_message=original,
        artifact_snapshot={"summary_title": "Original"}, status="completed",
    )
    RelayDelivery.objects.create(
        event=prior, subscription=subscription, target_type=target_type,
        status="success", external_id="original-record",
        idempotency_key="original-delivery",
    )
    # A later delivery in another subscription must not become the target.
    other_subscription = RelaySubscription.objects.create(
        user=user, name="other", target_type=target_type, enabled=False,
    )
    RelayDelivery.objects.create(
        event=prior, subscription=other_subscription, target_type=target_type,
        status="success", external_id="unrelated-record",
        idempotency_key="other-delivery",
    )
    snapshot = {
        "summary_title": "Follow-up", "trigger_source": trigger_source,
    }
    event = RelayEvent.objects.create(
        user=user, email_message=follow_up, artifact_snapshot=snapshot,
    )
    adapter = Mock()

    def deliver(**kwargs):
        delivery = kwargs["delivery"]
        plan = delivery.metadata["relay_delivery_plan"]
        assert plan["action"] == "update"
        assert plan["source"] == ("retry" if trigger_source else "auto_merge")
        assert plan["reference_external_id"] == "original-record"
        assert delivery.external_id == "original-record"
        return SimpleNamespace(
            external_id="original-record",
            external_url="https://example.com/original-record", metadata={},
        )

    adapter.deliver.side_effect = deliver
    monkeypatch.setattr(
        "relay.services.adapters.RelayAdapterRegistry.get_adapter",
        lambda target: adapter,
    )

    first = RelayDispatcher.dispatch_event(event)
    duplicate = RelayEvent.objects.create(
        user=user, email_message=follow_up, artifact_snapshot=snapshot,
    )
    second = RelayDispatcher.dispatch_event(duplicate)

    assert first["success"] == 1
    assert second["skipped"] == 1
    adapter.deliver.assert_called_once()
    assert RelayDelivery.objects.filter(subscription=subscription).count() == 2


@pytest.mark.django_db
def test_manual_canonical_message_still_creates_and_links(
    django_user_model, monkeypatch,
):
    user = django_user_model.objects.create_user("manual-merge-delivery")
    canonical = EmailMessage.objects.create(
        user=user, message_id="manual-canonical", received_at=timezone.now(),
    )
    source = EmailMessage.objects.create(
        user=user, message_id="manual-source", received_at=timezone.now(),
        merged_into=canonical, merge_reason="manual",
    )
    subscription = RelaySubscription.objects.create(
        user=user, name="manual", target_type="jira",
        strategies={
            "auto_merge_strategy": "update", "manual_merge_strategy": "linked",
        },
    )
    prior = RelayEvent.objects.create(user=user, email_message=source)
    RelayDelivery.objects.create(
        event=prior, subscription=subscription, target_type="jira",
        status="success", external_id="REQ-original",
        idempotency_key="manual-original",
    )
    event = RelayEvent.objects.create(user=user, email_message=canonical)
    adapter = Mock()
    adapter.deliver.return_value = SimpleNamespace(
        external_id="REQ-manual", external_url="https://example.com/manual",
        metadata={},
    )
    monkeypatch.setattr(
        "relay.services.adapters.RelayAdapterRegistry.get_adapter",
        lambda target: adapter,
    )

    result = RelayDispatcher.dispatch_event(event)

    assert result["success"] == 1
    plan = adapter.deliver.call_args.kwargs["delivery"].metadata[
        "relay_delivery_plan"
    ]
    assert plan["action"] == "new_and_link"
    assert plan["source"] == "manual_merge"
    assert plan["related_issue_keys"] == ["REQ-original"]

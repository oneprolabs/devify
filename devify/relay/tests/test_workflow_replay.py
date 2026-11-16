"""Different events representing one workflow result must deliver only once."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from relay.models import RelayDelivery, RelayEvent, RelaySubscription
from relay.services.dispatcher import RelayDispatcher
from relay.services.publisher import RelayEventPublisher
from threadline.models import EmailMessage

pytestmark = pytest.mark.django_db


@pytest.fixture
def email():
    user = get_user_model().objects.create_user("relay-replay", password="x")
    return EmailMessage.objects.create(
        user=user, message_id="relay-replay", subject="Replay",
        sender="a@example.com", recipients="b@example.com",
        received_at=timezone.now(),
    )


@pytest.fixture
def adapter(monkeypatch):
    adapter = Mock()
    adapter.deliver.return_value = SimpleNamespace(
        external_id="issue-1", external_url="https://example.com/issue-1",
        metadata={},
    )
    monkeypatch.setattr(
        "relay.services.adapters.RelayAdapterRegistry.get_adapter",
        lambda target: adapter,
    )
    return adapter


def test_publisher_reuses_existing_result_with_different_trigger(email):
    state = {"id": email.pk, "user_id": email.user_id,
             "summary_title": "Same result", "trigger_source": None}
    first = RelayEventPublisher.publish_workflow_completed(
        email=email, state=state
    )
    state["trigger_source"] = "retry_task"
    second = RelayEventPublisher.publish_workflow_completed(
        email=email, state=state
    )
    assert first.pk == second.pk
    assert RelayEvent.objects.filter(email_message=email).count() == 1


def test_changed_result_still_publishes_a_new_event(email):
    first = RelayEventPublisher.publish_workflow_completed(
        email=email, state={"summary_title": "Before"}
    )
    second = RelayEventPublisher.publish_workflow_completed(
        email=email, state={"summary_title": "Corrected"}
    )
    assert first.pk != second.pk


@pytest.mark.parametrize("legacy_status", [None, "success", "processing"])
def test_duplicate_events_share_a_delivery(email, adapter, legacy_status):
    subscription = RelaySubscription.objects.create(
        user=email.user, name="Replay regression", target_type="jira",
        config={"project_key": "TEST"}, enabled=True,
    )
    first = RelayEvent.objects.create(
        user=email.user, email_message=email,
        artifact_snapshot={"summary_title": "Same result"},
    )
    second = RelayEvent.objects.create(
        user=email.user, email_message=email,
        artifact_snapshot={"summary_title": "Same result"},
    )
    if legacy_status:
        RelayDelivery.objects.create(
            event=first, subscription=subscription, target_type="jira",
            idempotency_key=f"{first.pk}:{subscription.pk}",
            status=legacy_status,
        )
    else:
        RelayDispatcher.dispatch_event(first)
    result = RelayDispatcher.dispatch_event(second)
    assert result["skipped"] == 1
    assert adapter.deliver.call_count == (0 if legacy_status else 1)
    assert RelayDelivery.objects.filter(subscription=subscription).count() == 1
    second.refresh_from_db()
    assert second.status == (
        "processing" if legacy_status == "processing" else "completed"
    )


def test_cached_todo_records_do_not_make_a_new_business_result(email):
    original = {"content": "Review proposal", "owner": "Alice",
                "priority": "high", "location": "",
                "deadline_original": "tomorrow",
                "deadline_processed": "2026-11-17T12:00:00+00:00"}
    cached = {"content": "Review proposal", "owner": "Alice",
              "priority": "high", "location": None, "id": "record-1",
              "deadline": "2026-11-17T12:00:00Z", "is_completed": False,
              "completed_at": None, "metadata": {}}
    first = RelayEventPublisher.publish_workflow_completed(
        email=email, state={"todos": [original]}
    )
    second = RelayEventPublisher.publish_workflow_completed(
        email=email, state={"todos": [cached]}
    )
    assert first.pk == second.pk

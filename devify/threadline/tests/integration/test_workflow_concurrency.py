"""Exercise real MariaDB claims without flushing the provided database."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest
from django.contrib.auth import get_user_model
from django.db import close_old_connections, connection
from django.utils import timezone

from relay.models import RelayDelivery, RelayEvent, RelaySubscription
from relay.services.dispatcher import RelayDispatcher
from relay.services.publisher import RelayEventPublisher
from threadline.models import EmailMessage
from threadline.services.workflow_recovery import claim_workflow

pytestmark = pytest.mark.integration


@pytest.fixture
def committed_email(django_db_setup, django_db_blocker):
    # Thread connections must see committed rows. Create and remove only
    # records owned by this test; transaction=True would flush live data.
    with django_db_blocker.unblock():
        assert not connection.in_atomic_block
        key = f"replay-concurrency-{uuid4().hex}"
        user = get_user_model().objects.create_user(key)
        try:
            email = EmailMessage.objects.create(
                user=user, message_id=key, subject="Concurrency regression",
                sender="a@example.com", recipients="b@example.com",
                received_at=timezone.now(), status="fetched",
            )
            yield email
        finally:
            user.delete()


def race(action):
    barrier = Barrier(2)

    def run(_):
        close_old_connections()
        try:
            barrier.wait(timeout=10)
            return action()
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        return list(pool.map(run, range(2)))


def test_concurrent_workflow_claim_has_one_winner(committed_email):
    results = race(lambda: claim_workflow(committed_email.pk))
    assert sorted(results) == [False, True]


def test_concurrent_completion_publishes_one_event(
    committed_email, monkeypatch
):
    monkeypatch.setattr("relay.tasks.process_relay_event.delay", Mock())
    ids = race(lambda: RelayEventPublisher.publish_workflow_completed(
        email=committed_email, state={"summary_title": "Same result"}
    ).pk)
    assert len(set(ids)) == 1


def test_concurrent_events_deliver_once(committed_email, monkeypatch):
    adapter = Mock()
    adapter.deliver.return_value = SimpleNamespace(
        external_id="issue-1", external_url="https://example.com/issue-1",
        metadata={},
    )
    monkeypatch.setattr(
        "relay.services.adapters.RelayAdapterRegistry.get_adapter",
        lambda target: adapter,
    )
    subscription = RelaySubscription.objects.create(
        user=committed_email.user, name="Concurrency", target_type="jira",
        config={"project_key": "TEST"}, enabled=True,
    )
    events = [RelayEvent.objects.create(
        user=committed_email.user, email_message=committed_email,
        artifact_snapshot={"summary_title": "Same result"},
    ) for _ in range(2)]
    # Distinct events recreate the historical duplicate-event failure.
    queued = iter(events)
    race(lambda: RelayDispatcher.dispatch_event(next(queued)))
    assert adapter.deliver.call_count == 1
    assert RelayDelivery.objects.filter(subscription=subscription).count() == 1

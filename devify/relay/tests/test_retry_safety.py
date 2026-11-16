"""Explicit delivery retries own a durable request before publication."""

from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest
from agentcore_task.adapters.django.models import TaskExecution
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from relay.models import RelayDelivery, RelayEvent, RelaySubscription
from relay.services.dispatcher import RelayDispatcher
from relay.tasks import process_relay_delivery
from threadline.models import EmailMessage

pytestmark = pytest.mark.django_db


@pytest.fixture
def delivery(monkeypatch):
    key = 'relay-retry-' + uuid4().hex
    user = get_user_model().objects.create_user(key)
    email = EmailMessage.objects.create(
        user=user,
        message_id=key,
        subject='Retry regression',
        sender='a@example.com',
        recipients='b@example.com',
        received_at=timezone.now(),
    )
    subscription = RelaySubscription.objects.create(
        user=user,
        name='Retry',
        target_type='jira',
    )
    event = RelayEvent.objects.create(user=user, email_message=email)
    return RelayDelivery.objects.create(
        event=event,
        subscription=subscription,
        target_type='jira',
        status='failed',
        idempotency_key=f'{event.pk}:{subscription.pk}',
    )


@pytest.fixture
def adapter(monkeypatch):
    adapter = Mock()
    adapter.deliver.return_value = SimpleNamespace(
        external_id='issue-1',
        external_url='https://example.com/issue-1',
        metadata={},
    )
    monkeypatch.setattr(
        'relay.services.adapters.RelayAdapterRegistry.get_adapter',
        lambda target: adapter,
    )
    return adapter


def test_http_retry_reuses_queued_request_but_allows_new_explicit_retry(
    delivery,
    adapter,
    django_capture_on_commit_callbacks,
):
    client = APIClient()
    client.force_authenticate(user=delivery.event.user)
    url = reverse('relay-delivery-retry', kwargs={'pk': delivery.pk})
    with (
        patch('relay.tasks.process_relay_delivery.apply_async') as send,
        django_capture_on_commit_callbacks(execute=True),
    ):
        first = client.post(url)
        second = client.post(url)
    assert first.status_code == second.status_code == 202
    first_id = first.data['data']['task_id']
    assert first_id == second.data['data']['task_id']
    send.assert_called_once()
    for _ in range(2):
        process_relay_delivery.apply(
            args=[str(delivery.pk)],
            task_id=first_id,
            throw=True,
        ).get()
    assert adapter.deliver.call_count == 1
    with (
        patch('relay.tasks.process_relay_delivery.apply_async') as send,
        django_capture_on_commit_callbacks(execute=True),
    ):
        third = client.post(url)
    assert third.status_code == 202
    assert third.data['data']['task_id'] != first_id
    send.assert_called_once()


def test_failed_publication_releases_delivery_reservation(
    delivery,
    django_capture_on_commit_callbacks,
):
    with (
        patch(
            'relay.tasks.process_relay_delivery.apply_async',
            side_effect=RuntimeError('broker unavailable'),
        ),
        pytest.raises(RuntimeError, match='broker unavailable'),
        django_capture_on_commit_callbacks(execute=True),
    ):
        RelayDispatcher.enqueue_retry(delivery)
    delivery.refresh_from_db()
    assert delivery.status == 'failed'
    assert (
        TaskExecution.objects.get(task_id=delivery.agentcore_task_id).status
        == 'FAILURE'
    )


def test_superseded_request_cannot_deliver_for_new_request(
    delivery,
    adapter,
    django_capture_on_commit_callbacks,
):
    with (
        patch('relay.tasks.process_relay_delivery.apply_async'),
        django_capture_on_commit_callbacks(execute=True),
    ):
        old_id = RelayDispatcher.enqueue_retry(delivery)
        TaskExecution.objects.filter(task_id=old_id).update(status='FAILURE')
        RelayDelivery.objects.filter(pk=delivery.pk).update(status='failed')
        new_id = RelayDispatcher.enqueue_retry(delivery)
    process_relay_delivery.apply(
        args=[str(delivery.pk)],
        task_id=old_id,
        throw=True,
    ).get()
    adapter.deliver.assert_not_called()
    process_relay_delivery.apply(
        args=[str(delivery.pk)],
        task_id=new_id,
        throw=True,
    ).get()
    adapter.deliver.assert_called_once()

"""Exercise the dispatchers as well as their Celery entry points."""

from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest
from agentcore_task.adapters.django.models import TaskExecution
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from relay.models import RelayDelivery, RelayEvent, RelaySubscription
from relay.tasks import process_relay_delivery
from threadline.models import EmailMessage
from threadline.services.merge_workflow import enqueue_merge_workflow
from threadline.services.workflow_recovery import (
    child_workflow_id,
    claim_workflow,
)
from threadline.tasks.email_merge import process_email_merge
from threadline.tasks.email_workflow import (
    process_email_workflow,
    retry_failed_email_workflow,
)

pytestmark = [pytest.mark.integration, pytest.mark.django_db]


@pytest.fixture
def email(django_user_model):
    key = 'retry-entrypoint-' + uuid4().hex
    user = django_user_model.objects.create_user(key)
    return EmailMessage.objects.create(
        user=user,
        message_id=key,
        subject='Retry regression',
        sender='a@example.com',
        recipients='b@example.com',
        received_at=timezone.now(),
        status='fetched',
    )


@pytest.mark.parametrize('force', [False, True])
@pytest.mark.parametrize('initial_status', ['fetched', 'success', 'failed'])
def test_queued_ui_request_runs_and_redelivery_is_skipped(
    email,
    force,
    initial_status,
    django_capture_on_commit_callbacks,
):
    EmailMessage.objects.filter(pk=email.pk).update(status=initial_status)
    email.refresh_from_db()
    with (
        patch(
            'threadline.tasks.email_merge.process_email_merge.apply_async'
        ) as send,
        patch(
            'threadline.tasks.email_merge.process_email_merge.delay'
        ) as old_send,
        django_capture_on_commit_callbacks(execute=True),
    ):
        enqueue_merge_workflow(email, force=force, trigger_source='api_retry')
    assert send.call_count + old_send.call_count == 1

    def complete(**kwargs):
        EmailMessage.objects.filter(pk=email.pk).update(status='success')
        return {'success': True}

    queued = []
    with (
        patch(
            'threadline.tasks.email_merge.EmailMergeService.reconcile',
            return_value=(
                email,
                SimpleNamespace(should_merge=False, reason='', sources=[]),
            ),
        ),
        patch(
            'threadline.tasks.email_merge.process_email_workflow.apply_async',
            side_effect=lambda **kwargs: queued.append(kwargs),
        ),
        patch(
            'threadline.tasks.email_merge.process_email_workflow.delay',
            side_effect=lambda *args, **kwargs: queued.append(
                {'args': args, 'kwargs': kwargs, 'task_id': uuid4().hex}
            ),
        ),
    ):
        parent_id = (
            send.call_args.kwargs['task_id'] if send.called else uuid4().hex
        )
        process_email_merge.apply(
            args=[str(email.pk)],
            kwargs={'force': force, 'trigger_source': 'api_retry'},
            task_id=parent_id,
            throw=True,
        ).get()
    assert len(queued) == 1
    with patch(
        'threadline.tasks.email_workflow.execute_email_processing_workflow',
        side_effect=complete,
    ) as run:
        for _ in range(2):
            process_email_workflow.apply(**queued[0], throw=True).get()
    run.assert_called_once()
    assert run.call_args.kwargs['force'] is force
    email.refresh_from_db()
    assert email.status == 'success'


def test_busy_email_does_not_enqueue_another_ui_request(
    email,
    django_capture_on_commit_callbacks,
):
    EmailMessage.objects.filter(pk=email.pk).update(status='processing')
    # A stale request-side object must not reset an active execution.
    with (
        patch(
            'threadline.tasks.email_merge.process_email_merge.apply_async'
        ) as send,
        patch(
            'threadline.tasks.email_merge.process_email_merge.delay'
        ) as old_send,
        django_capture_on_commit_callbacks(execute=True),
    ):
        enqueue_merge_workflow(email, force=True)
    send.assert_not_called()
    old_send.assert_not_called()


def test_redelivered_force_merge_does_not_enqueue_twice(email):
    with (
        patch(
            'threadline.tasks.email_merge.EmailMergeService.reconcile',
            return_value=(
                email,
                SimpleNamespace(should_merge=False, reason='', sources=[]),
            ),
        ),
        patch(
            'threadline.tasks.email_merge.process_email_workflow.apply_async'
        ) as send,
        patch(
            'threadline.tasks.email_merge.process_email_workflow.delay'
        ) as old_send,
    ):
        request_id = uuid4().hex
        for _ in range(2):
            process_email_merge.apply(
                args=[str(email.pk)],
                kwargs={'force': True},
                task_id=request_id,
                throw=True,
            ).get()
    assert send.call_count + old_send.call_count == 1


def test_redelivered_delivery_retry_does_not_send_twice(email, monkeypatch):
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
    subscription = RelaySubscription.objects.create(
        user=email.user,
        name='Retry',
        target_type='jira',
        config={'project_key': 'TEST'},
    )
    event = RelayEvent.objects.create(
        user=email.user,
        email_message=email,
        artifact_snapshot={'summary_title': 'Same result'},
    )
    delivery = RelayDelivery.objects.create(
        event=event,
        subscription=subscription,
        target_type='jira',
        status='failed',
        idempotency_key=f'{event.pk}:{subscription.pk}',
    )
    request_id = uuid4().hex
    for _ in range(2):
        process_relay_delivery.apply(
            args=[str(delivery.pk)], task_id=request_id, throw=True
        ).get()
    assert adapter.deliver.call_count == 1
    # A genuinely new explicit retry remains available.
    process_relay_delivery.apply(
        args=[str(delivery.pk)], task_id=uuid4().hex, throw=True
    ).get()
    assert adapter.deliver.call_count == 2
    assert TaskExecution.objects.filter(
        task_id=request_id, status='SUCCESS'
    ).exists()


@pytest.mark.parametrize('entrypoint', ['create', 'retry', 'batch_retry'])
def test_http_dispatch_reserves_a_claimable_workflow(
    email,
    entrypoint,
    django_capture_on_commit_callbacks,
):
    client = APIClient()
    client.force_authenticate(user=email.user)
    if entrypoint == 'create':
        url = reverse('threadlines-list')
        payload = {
            'subject': 'HTTP regression',
            'sender': 'a@example.com',
            'recipients': 'b@example.com',
            'message_id': uuid4().hex,
            'received_at': timezone.now().isoformat(),
            'text_content': 'Test',
        }
    elif entrypoint == 'retry':
        url = reverse('threadlines-retry', kwargs={'uuid': email.uuid})
        payload = {}
    else:
        url = reverse('threadlines-batch-retry')
        payload = {'source_uuids': [str(email.uuid)]}
    with (
        patch(
            'threadline.tasks.email_merge.process_email_merge.apply_async'
        ) as send,
        django_capture_on_commit_callbacks(execute=True),
    ):
        response = client.post(url, payload, format='json')
    assert response.status_code in [200, 201], response.data
    send.assert_called_once()
    queued = send.call_args.kwargs
    target = queued['args'][0]
    assert claim_workflow(target, task_id=child_workflow_id(queued['task_id']))


def test_parent_republication_keeps_the_same_child_id(email):
    with (
        patch(
            'threadline.tasks.email_merge.EmailMergeService.reconcile',
            return_value=(
                email,
                SimpleNamespace(should_merge=False, reason='', sources=[]),
            ),
        ),
        patch(
            'threadline.tasks.email_merge.process_email_workflow.apply_async'
        ) as send,
    ):
        parent_id = uuid4().hex
        process_email_merge.apply(
            args=[str(email.pk)],
            kwargs={'force': True},
            task_id=parent_id,
            throw=True,
        ).get()
        # A crash after publication may leave no completed parent trace.
        TaskExecution.objects.filter(task_id=parent_id).delete()
        process_email_merge.apply(
            args=[str(email.pk)],
            kwargs={'force': True},
            task_id=parent_id,
            throw=True,
        ).get()
    ids = [call.kwargs['task_id'] for call in send.call_args_list]
    assert len(ids) == 2 and ids[0] == ids[1]


def test_retry_wrapper_republication_keeps_the_same_child_id(email):
    with patch(
        'threadline.tasks.email_workflow.process_email_workflow.apply_async'
    ) as send:
        parent_id = uuid4().hex
        for _ in range(2):
            retry_failed_email_workflow.apply(
                args=[str(email.pk)],
                task_id=parent_id,
                throw=True,
            ).get()
    ids = [call.kwargs['task_id'] for call in send.call_args_list]
    assert len(ids) == 2 and ids[0] == ids[1]


def test_failed_broker_dispatch_releases_the_ui_reservation(
    email,
    django_capture_on_commit_callbacks,
):
    with (
        patch(
            'threadline.tasks.email_merge.process_email_merge.apply_async',
            side_effect=RuntimeError('broker unavailable'),
        ),
        pytest.raises(RuntimeError, match='broker unavailable'),
        django_capture_on_commit_callbacks(execute=True),
    ):
        enqueue_merge_workflow(email)
    email.refresh_from_db()
    assert email.status == 'failed'
    assert (
        TaskExecution.objects.filter(
            created_by=email.user,
            status='FAILURE',
        ).count()
        == 1
    )

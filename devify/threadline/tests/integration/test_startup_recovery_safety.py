"""Startup recovery must observe the same boundaries as periodic recovery."""

from datetime import timedelta
from unittest.mock import patch
from uuid import uuid4

import pytest
from django.utils import timezone

from threadline.models import EmailMessage
from threadline.services.merge_workflow import enqueue_merge_workflow
from threadline.services.startup_recovery import (
    recover_stuck_processing_emails,
)
from threadline.services.workflow_recovery import claim_workflow

pytestmark = [pytest.mark.integration, pytest.mark.django_db]


@pytest.fixture
def stale_email(django_user_model):
    key = 'startup-safety-' + uuid4().hex
    user = django_user_model.objects.create_user(key)
    email = EmailMessage.objects.create(
        user=user,
        message_id=key,
        subject='Recovery regression',
        sender='a@example.com',
        recipients='b@example.com',
        received_at=timezone.now(),
        status='processing',
    )
    EmailMessage.objects.filter(pk=email.pk).update(
        updated_at=timezone.now() - timedelta(hours=1),
    )
    return email


@pytest.mark.parametrize(
    'inspection', [None, 'queued', 'paused', 'historical']
)
def test_startup_recovery_leaves_uneligible_work_untouched(
    stale_email,
    inspection,
):
    email = stale_email
    if inspection == 'historical':
        EmailMessage.objects.filter(pk=email.pk).update(
            updated_at=timezone.now() - timedelta(days=4),
        )
    with (
        patch(
            'threadline.services.startup_recovery.workflows_in_flight',
            return_value=(
                None
                if inspection is None
                else {str(email.pk)} if inspection == 'queued' else set()
            ),
        ),
        patch(
            'threadline.services.startup_recovery.paused_user_ids',
            return_value={email.user_id} if inspection == 'paused' else set(),
        ),
        patch(
            'threadline.services.startup_recovery.process_email_merge.delay'
        ) as send,
    ):
        recover_stuck_processing_emails(timeout_minutes=30)
    send.assert_not_called()
    email.refresh_from_db()
    assert email.status == 'processing'


def test_startup_recovery_does_not_overwrite_concurrent_completion(
    stale_email,
):
    def complete():
        EmailMessage.objects.filter(pk=stale_email.pk).update(
            status='success',
            updated_at=timezone.now(),
        )
        return set()

    with (
        patch(
            'threadline.services.startup_recovery.workflows_in_flight',
            side_effect=complete,
        ),
        patch(
            'threadline.services.startup_recovery.process_email_merge.delay'
        ) as send,
    ):
        recover_stuck_processing_emails(timeout_minutes=30)
    send.assert_not_called()
    stale_email.refresh_from_db()
    assert stale_email.status == 'success'


def test_startup_retires_abandoned_request_before_requeue(
    stale_email,
    django_capture_on_commit_callbacks,
):
    EmailMessage.objects.filter(pk=stale_email.pk).update(status='failed')
    with (
        patch('threadline.tasks.email_merge.process_email_merge.apply_async'),
        django_capture_on_commit_callbacks(execute=True),
    ):
        email = enqueue_merge_workflow(stale_email)
    request_id = email.metadata['processing_progress']['task_id']
    EmailMessage.objects.filter(pk=email.pk).update(
        updated_at=timezone.now() - timedelta(hours=1),
    )
    with (
        patch(
            'threadline.services.startup_recovery.workflows_in_flight',
            return_value=set(),
        ),
        patch(
            'threadline.services.startup_recovery.process_email_merge.delay'
        ) as send,
    ):
        result = recover_stuck_processing_emails(timeout_minutes=30)
    assert result['requeued_count'] == 1
    send.assert_called_once()
    email.refresh_from_db()
    assert email.status == 'failed'
    assert not claim_workflow(email.pk, task_id=request_id)
    assert claim_workflow(email.pk)


def test_worker_ready_defers_recovery_until_control_loop_can_reply():
    from threadline.celery_bootstrap import (
        recover_processing_emails_on_worker_ready,
    )

    with patch(
        'threadline.tasks.scheduler.'
        'recover_email_workflows_after_startup.apply_async'
    ) as send:
        recover_processing_emails_on_worker_ready()
    send.assert_called_once_with(countdown=10)

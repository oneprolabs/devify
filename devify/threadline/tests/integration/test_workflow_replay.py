"""Recovery must not replay successful, queued or currently running mail."""

from datetime import timedelta
from unittest.mock import patch
from uuid import uuid4

import pytest
from django.utils import timezone

from threadline.models import EmailMessage
from threadline.services.workflow_recovery import claim_workflow
from threadline.tasks.email_workflow import process_email_workflow
from threadline.tasks.scheduler import schedule_reset_stuck_processing_emails

pytestmark = [pytest.mark.integration, pytest.mark.django_db]
RUN = "threadline.tasks.email_workflow.execute_email_processing_workflow"
PENDING = "threadline.tasks.scheduler.workflows_in_flight"


@pytest.fixture
def email(django_user_model):
    user = django_user_model.objects.create_user(
        "workflow-replay", password="x"
    )
    return EmailMessage.objects.create(
        user=user, message_id="workflow-replay", subject="Replay regression",
        sender="a@example.com", recipients="b@example.com",
        received_at=timezone.now(), status="fetched",
    )


def test_sequential_duplicate_runs_workflow_only_once(email):
    def complete(**kwargs):
        EmailMessage.objects.filter(pk=email.pk).update(status="success")
        return {"success": True}

    with patch(RUN, side_effect=complete) as run:
        process_email_workflow(str(email.pk))
        process_email_workflow(str(email.pk))
    run.assert_called_once()
    email.refresh_from_db()
    assert email.status == "success"


def test_running_email_cannot_be_claimed_again(email):
    assert claim_workflow(email.pk)
    assert not claim_workflow(email.pk)
    assert not claim_workflow(email.pk, force=True)
    with patch(RUN) as run:
        process_email_workflow(str(email.pk))
    run.assert_not_called()


def test_explicit_retry_can_claim_a_completed_email(email):
    EmailMessage.objects.filter(pk=email.pk).update(status="success")
    with patch(RUN, return_value={"success": True}) as run:
        process_email_workflow(str(email.pk), force=True)
    run.assert_called_once()


def test_unexpected_failure_releases_processing_claim(email):
    with patch(RUN, side_effect=RuntimeError("workflow crashed")):
        with pytest.raises(RuntimeError, match="workflow crashed"):
            process_email_workflow(str(email.pk))
    email.refresh_from_db()
    assert email.status == "failed"
    assert claim_workflow(email.pk)


@pytest.mark.parametrize(
    ("status", "retries"), [("fetched", 0), ("fetched", 1), ("processing", 0)]
)
def test_recovery_leaves_queued_or_active_work_untouched(
    email, status, retries
):
    EmailMessage.objects.filter(pk=email.pk).update(
        status=status, fetch_retry_count=retries,
        updated_at=timezone.now() - timedelta(hours=1),
    )
    with (
        patch(PENDING, return_value={str(email.pk)}),
        patch(
            "threadline.tasks.scheduler.process_email_workflow.delay"
        ) as send,
    ):
        schedule_reset_stuck_processing_emails()
    send.assert_not_called()
    email.refresh_from_db()
    assert email.status == status
    assert email.fetch_retry_count == retries


def test_recovery_postpones_when_queue_inspection_fails(email):
    EmailMessage.objects.filter(pk=email.pk).update(
        updated_at=timezone.now() - timedelta(hours=1)
    )
    with (
        patch(PENDING, return_value=None),
        patch(
            "threadline.tasks.scheduler.process_email_workflow.delay"
        ) as send,
    ):
        result = schedule_reset_stuck_processing_emails()
    send.assert_not_called()
    assert result == {"status": "skipped", "reason": "inspection_unavailable"}
    email.refresh_from_db()
    assert email.fetch_retry_count == 0


def test_redelivered_explicit_retry_does_not_execute_twice(email):
    def complete(**kwargs):
        EmailMessage.objects.filter(pk=email.pk).update(status="success")
        return {"success": True}

    task_id = uuid4().hex
    with patch(RUN, side_effect=complete) as run:
        for _ in range(2):
            process_email_workflow.apply(
                args=[str(email.pk)], kwargs={"force": True},
                task_id=task_id, throw=True,
            ).get()
    run.assert_called_once()


def test_recovery_does_not_overwrite_completion_during_the_sweep(email):
    other = EmailMessage.objects.create(
        user=email.user, message_id="workflow-replay-other", subject="Other",
        sender="a@example.com", recipients="b@example.com",
        received_at=timezone.now(), status="fetched",
    )
    ids = {email.pk, other.pk}
    EmailMessage.objects.filter(pk__in=ids).update(
        updated_at=timezone.now() - timedelta(hours=1)
    )

    def finish_other(email_id):
        EmailMessage.objects.filter(pk__in=ids).exclude(pk=email_id).update(
            status="success", updated_at=timezone.now()
        )

    with (
        patch(PENDING, return_value=set()),
        patch(
            "threadline.tasks.scheduler.process_email_workflow.delay",
            side_effect=finish_other,
        ) as send,
    ):
        schedule_reset_stuck_processing_emails()
    queued = [call.args[0] for call in send.call_args_list
              if int(call.args[0]) in ids]
    assert len(queued) == 1
    assert EmailMessage.objects.filter(
        pk__in=ids, status="success", fetch_retry_count=0
    ).count() == 1

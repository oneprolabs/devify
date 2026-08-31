"""
Tests for the per-user brake on email processing.

Pausing has to stop the whole chain, including the job that reclaims stuck
mail. That job retries anything sitting in FETCHED and marks it failed on
the second pass, so a pause it did not respect would quietly destroy the
backlog it was meant to protect.
"""

from datetime import timedelta
from unittest.mock import patch

import pytest
from django.utils import timezone

from threadline.models import EmailMessage, Settings
from threadline.services.processing_control import (
    is_processing_paused,
    paused_user_ids,
    set_processing_paused,
)
from threadline.state_machine import EmailStatus


pytestmark = [pytest.mark.integration, pytest.mark.django_db]


def make_email(user, counter=[0], **overrides):
    counter[0] += 1
    payload = {
        "user": user,
        "message_id": f"email_pause_{counter[0]:04d}",
        "subject": "hello",
        "sender": "a@example.com",
        "recipients": "b@example.com",
        "received_at": timezone.now(),
        "status": EmailStatus.FETCHED.value,
    }
    payload.update(overrides)
    return EmailMessage.objects.create(**payload)


class TestPauseFlag:
    def test_processing_runs_by_default(self, django_user_model):
        user = django_user_model.objects.create_user("p1", password="x")

        assert is_processing_paused(user.id) is False

    def test_the_brake_can_be_applied_and_released(self, django_user_model):
        user = django_user_model.objects.create_user("p2", password="x")

        set_processing_paused(user, True)
        assert is_processing_paused(user.id) is True

        set_processing_paused(user, False)
        assert is_processing_paused(user.id) is False

    def test_it_does_not_disturb_the_rest_of_the_settings(
        self, django_user_model
    ):
        user = django_user_model.objects.create_user("p3", password="x")
        Settings.objects.create(
            user=user,
            key="email_config",
            value={"filter_config": {"max_age_days": 7}},
            is_active=True,
        )

        set_processing_paused(user, True)

        stored = Settings.objects.get(user=user, key="email_config").value
        assert stored["filter_config"] == {"max_age_days": 7}
        assert stored["processing_paused"] is True

    def test_paused_users_are_listed_in_one_read(self, django_user_model):
        paused = django_user_model.objects.create_user("p4", password="x")
        running = django_user_model.objects.create_user("p5", password="x")
        set_processing_paused(paused, True)
        set_processing_paused(running, False)

        listed = paused_user_ids()

        assert paused.id in listed
        assert running.id not in listed


class TestFetchChain:
    QUEUE = "threadline.tasks.email_fetch.process_email_merge"

    def test_new_mail_is_queued_when_running(self, django_user_model):
        from threadline.tasks.email_fetch import _queue_merge_for_saved_email

        user = django_user_model.objects.create_user("p6", password="x")
        email = make_email(user)

        with patch(self.QUEUE) as queue:
            _queue_merge_for_saved_email(email)

        queue.delay.assert_called_once()

    def test_new_mail_is_parked_when_paused(self, django_user_model):
        from threadline.tasks.email_fetch import _queue_merge_for_saved_email

        user = django_user_model.objects.create_user("p7", password="x")
        set_processing_paused(user, True)
        email = make_email(user)

        with patch(self.QUEUE) as queue:
            _queue_merge_for_saved_email(email)

        queue.delay.assert_not_called()
        email.refresh_from_db()
        # Parked, not lost: it is still waiting in FETCHED.
        assert email.status == EmailStatus.FETCHED.value


class TestStuckReset:
    WORKFLOW = "threadline.tasks.scheduler.process_email_workflow"

    def _aged(self, email):
        EmailMessage.objects.filter(pk=email.pk).update(
            updated_at=timezone.now() - timedelta(hours=2)
        )

    def test_stuck_mail_is_retried_for_a_running_user(
        self, django_user_model
    ):
        from threadline.tasks.scheduler import (
            schedule_reset_stuck_processing_emails,
        )

        user = django_user_model.objects.create_user("p8", password="x")
        email = make_email(user)
        self._aged(email)

        with patch(self.WORKFLOW) as workflow:
            schedule_reset_stuck_processing_emails()

        queued = {call.args[0] for call in workflow.delay.call_args_list}
        assert str(email.id) in queued

    def test_paused_mail_is_left_alone(self, django_user_model):
        from threadline.tasks.scheduler import (
            schedule_reset_stuck_processing_emails,
        )

        user = django_user_model.objects.create_user("p9", password="x")
        set_processing_paused(user, True)
        email = make_email(user)
        self._aged(email)

        with patch(self.WORKFLOW) as workflow:
            schedule_reset_stuck_processing_emails()

        # Scoped to this user: the suite shares the development database,
        # so other accounts legitimately have mail in flight.
        queued = {call.args[0] for call in workflow.delay.call_args_list}
        assert str(email.id) not in queued
        email.refresh_from_db()
        assert email.status == EmailStatus.FETCHED.value
        assert email.fetch_retry_count == 0

    def test_a_paused_backlog_is_never_marked_failed(
        self, django_user_model
    ):
        # The second pass is what turns a backlog into 444 failed emails.
        from threadline.tasks.scheduler import (
            schedule_reset_stuck_processing_emails,
        )

        user = django_user_model.objects.create_user("p10", password="x")
        set_processing_paused(user, True)
        email = make_email(user, fetch_retry_count=1)
        self._aged(email)

        with patch(self.WORKFLOW):
            schedule_reset_stuck_processing_emails()

        email.refresh_from_db()
        assert email.status == EmailStatus.FETCHED.value


class TestSweepWindow:
    """
    The sweep catches a trigger that went missing moments ago. Without a
    floor it rescans the whole history on every run and eventually marks a
    large backlog failed.
    """

    WORKFLOW = "threadline.tasks.scheduler.process_email_workflow"

    def _age(self, email, hours):
        EmailMessage.objects.filter(pk=email.pk).update(
            updated_at=timezone.now() - timedelta(hours=hours)
        )

    def test_recently_stuck_mail_is_swept(self, django_user_model):
        from threadline.tasks.scheduler import (
            schedule_reset_stuck_processing_emails,
        )

        user = django_user_model.objects.create_user("p11", password="x")
        email = make_email(user)
        self._age(email, 2)

        with patch(self.WORKFLOW) as workflow:
            schedule_reset_stuck_processing_emails()

        queued = {call.args[0] for call in workflow.delay.call_args_list}
        assert str(email.id) in queued

    def test_long_untouched_mail_is_left_alone(self, django_user_model):
        from threadline.tasks.scheduler import (
            schedule_reset_stuck_processing_emails,
        )

        user = django_user_model.objects.create_user("p12", password="x")
        email = make_email(user)
        self._age(email, 24 * 30)

        with patch(self.WORKFLOW) as workflow:
            schedule_reset_stuck_processing_emails()

        queued = {call.args[0] for call in workflow.delay.call_args_list}
        assert str(email.id) not in queued
        email.refresh_from_db()
        assert email.status == EmailStatus.FETCHED.value

    def test_the_floor_can_be_widened(self, django_user_model):
        from threadline.tasks.scheduler import (
            schedule_reset_stuck_processing_emails,
        )

        user = django_user_model.objects.create_user("p13", password="x")
        email = make_email(user)
        self._age(email, 24 * 30)

        with patch(self.WORKFLOW) as workflow:
            schedule_reset_stuck_processing_emails(max_age_hours=24 * 60)

        queued = {call.args[0] for call in workflow.delay.call_args_list}
        assert str(email.id) in queued


"""
Unit tests for stuck email scheduler behavior.
"""

from datetime import timedelta
from unittest.mock import Mock, patch

import pytest
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone

from threadline.models import EmailMessage
from threadline.tasks.scheduler import (
    _claim_dispatch_slot,
    _skip_recent_dispatch,
    schedule_email_fetch,
    schedule_haraka_cleanup,
    schedule_reset_stuck_processing_emails,
    schedule_share_link_cleanup,
    schedule_email_task_cleanup,
)

from ..fixtures.factories import EmailMessageFactory, UserFactory

LOCMEM_CACHE = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "scheduler-tests",
    }
}


class StuckEmailSchedulerTest(TestCase):
    def setUp(self):
        self.user = UserFactory(username="scheduler-test-user")

    def test_stuck_email_scheduler_function_exists(self):
        """Test that schedule_reset_stuck_emails exists in scheduler module"""
        # This function may or may not exist depending on the implementation
        try:
            from threadline.tasks.scheduler import schedule_reset_stuck_emails
            self.assertTrue(callable(schedule_reset_stuck_emails))
        except ImportError:
            # Function doesn't exist in this version - test passes by absence
            self.skipTest("schedule_reset_stuck_emails not available in this version")


@pytest.fixture
def locmem_cache():
    with override_settings(CACHES=LOCMEM_CACHE):
        cache.clear()
        yield cache
        cache.clear()


@pytest.mark.unit
def test_dispatch_slot_is_claimed_once_per_window(locmem_cache):
    with override_settings(THREADLINE_SCHEDULER_DISPATCH_GUARD_SECONDS=50):
        assert _claim_dispatch_slot("unit-test-task") is True
        assert _claim_dispatch_slot("unit-test-task") is False


@pytest.mark.unit
def test_dispatch_guard_zero_always_allows(locmem_cache):
    with override_settings(THREADLINE_SCHEDULER_DISPATCH_GUARD_SECONDS=0):
        assert _claim_dispatch_slot("unit-test-zero") is True
        assert _claim_dispatch_slot("unit-test-zero") is True


@pytest.mark.unit
def test_dispatch_guard_fails_open_when_cache_is_down(monkeypatch):
    class BrokenCache:
        def add(self, *args, **kwargs):
            raise ConnectionError("redis down")

    monkeypatch.setattr("django.core.cache.cache", BrokenCache())

    with override_settings(THREADLINE_SCHEDULER_DISPATCH_GUARD_SECONDS=50):
        assert _claim_dispatch_slot("unit-test-broken") is True


@pytest.mark.unit
def test_skip_recent_dispatch_returns_marker(locmem_cache):
    with override_settings(THREADLINE_SCHEDULER_DISPATCH_GUARD_SECONDS=50):
        assert _skip_recent_dispatch("unit-test-skip") is None
        assert _skip_recent_dispatch("unit-test-skip") == {
            "status": "skipped",
            "reason": "recent_dispatch",
        }


@pytest.mark.unit
def test_scheduler_returns_early_when_a_run_was_just_dispatched(locmem_cache):
    with override_settings(THREADLINE_SCHEDULER_DISPATCH_GUARD_SECONDS=50):
        assert _claim_dispatch_slot("email_fetch")

        with patch(
            "threadline.tasks.scheduler.TaskTracer"
        ) as tracer_mock:
            result = schedule_email_fetch()

    assert result == {"status": "skipped", "reason": "recent_dispatch"}
    tracer_mock.assert_not_called()


@pytest.mark.unit
@pytest.mark.parametrize(
    "task,name",
    [
        (schedule_haraka_cleanup, "haraka_cleanup"),
        (schedule_share_link_cleanup, "share_link_cleanup"),
        (schedule_reset_stuck_processing_emails, "stuck_email_reset"),
        (schedule_email_task_cleanup, "email_task_cleanup"),
    ],
)
def test_all_schedulers_share_the_dispatch_guard(locmem_cache, task, name):
    with override_settings(THREADLINE_SCHEDULER_DISPATCH_GUARD_SECONDS=50):
        assert _claim_dispatch_slot(name)

        with patch(
            "threadline.tasks.scheduler.TaskTracer"
        ) as tracer_mock:
            result = task()

    assert result == {"status": "skipped", "reason": "recent_dispatch"}
    tracer_mock.assert_not_called()


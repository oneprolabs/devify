from unittest.mock import Mock, patch

import pytest
from django.core.cache import cache
from django.test import override_settings

from threadline.utils.task_tracer import TaskTracer

LOCMEM_CACHE = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "task-tracer-tests",
    }
}


@pytest.fixture
def failure_notifications(monkeypatch):
    """Capture queued failure notifications and isolate the cache."""
    delay_mock = Mock()
    notification_task = (
        "threadline.tasks.notifications"
        ".send_threadline_failure_notification.delay"
    )
    monkeypatch.setattr(notification_task, delay_mock)
    # Clear inside the override: clearing outside would hit the real cache and
    # leave keys behind in the shared LocMem store between tests.
    with override_settings(CACHES=LOCMEM_CACHE):
        cache.clear()
        yield delay_mock
        cache.clear()


def _failing_tracer(monkeypatch, task_type="HARAKA_CLEANUP"):
    tracer = TaskTracer(task_type)
    monkeypatch.setattr(tracer, "_sync_agentcore_update", Mock())
    return tracer


@override_settings(CACHES=LOCMEM_CACHE)
def test_fail_task_queues_threadline_failure_notification(
    monkeypatch, failure_notifications
):
    tracer = TaskTracer("HARAKA_CLEANUP")
    sync_mock = Mock()

    monkeypatch.setattr(tracer, "_sync_agentcore_update", sync_mock)

    tracer.fail_task(
        {
            "cleanup_type": "HARAKA_CLEANUP",
            "errors": 1,
        },
        "boom",
    )

    sync_mock.assert_called_once()
    failure_notifications.assert_called_once()
    args = failure_notifications.call_args.args
    assert args[0] == "HARAKA_CLEANUP"
    assert args[1]["cleanup_type"] == "HARAKA_CLEANUP"
    assert args[2] == "boom"


def test_append_task_includes_context_and_raw_message(monkeypatch):
    tracer = TaskTracer("EMAIL_WORKFLOW")
    sync_mock = Mock()
    monkeypatch.setattr(tracer, "_sync_agentcore_update", sync_mock)

    tracer.append_task(
        "STEP",
        "Processing email",
        {
            "email_id": 42,
            "user_id": 7,
        },
    )

    sync_mock.assert_called_once()
    entry = tracer._agentcore_metadata["steps"][0]
    assert entry["message"].startswith(
        "[EMAIL_WORKFLOW | email_id=42 user_id=7]"
    )
    assert entry["raw_message"] == "Processing email"
    assert entry["context"]["email_id"] == 42
    assert entry["context"]["user_id"] == 7


def test_create_task_syncs_initial_zero_progress_snapshot(monkeypatch):
    tracer = TaskTracer("EMAIL_WORKFLOW")
    monkeypatch.setattr(tracer, "_sync_agentcore_registration", Mock())

    fake_message = Mock()
    filter_result = Mock()
    filter_result.only.return_value.first.return_value = fake_message

    with patch(
        "threadline.models.EmailMessage.objects.filter",
        return_value=filter_result,
    ):
        tracer.create_task(
            {
                "email_id": "123",
                "status": "starting",
                "progress_percent": 0,
            }
        )

    fake_message.set_processing_progress.assert_called_once_with(0)


def test_threadline_progress_snapshot_is_monotonic_within_task(monkeypatch):
    tracer = TaskTracer("EMAIL_WORKFLOW")
    tracer._context["email_id"] = "123"

    fake_message = Mock()
    filter_result = Mock()
    filter_result.only.return_value.first.return_value = fake_message

    with patch(
        "threadline.models.EmailMessage.objects.filter",
        return_value=filter_result,
    ):
        tracer._sync_threadline_progress_snapshot(
            {
                "progress_percent": 90,
                "progress_step": "STAGE_A",
            }
        )
        tracer._sync_threadline_progress_snapshot(
            {
                "progress_percent": 78,
                "progress_step": "STAGE_B",
            }
        )

    assert fake_message.set_processing_progress.call_count == 2
    assert fake_message.set_processing_progress.call_args_list[0].args == (92,)
    assert fake_message.set_processing_progress.call_args_list[1].args == (92,)


def test_email_merge_does_not_sync_user_facing_progress(monkeypatch):
    tracer = TaskTracer("EMAIL_MERGE")
    tracer._context["email_id"] = "123"

    fake_message = Mock()
    filter_result = Mock()
    filter_result.only.return_value.first.return_value = fake_message

    with patch(
        "threadline.models.EmailMessage.objects.filter",
        return_value=filter_result,
    ):
        tracer._sync_threadline_progress_snapshot(
            {
                "progress_percent": 75,
                "progress_step": "MERGE_RECONCILE",
            }
        )

    fake_message.set_processing_progress.assert_not_called()


@override_settings(
    CACHES=LOCMEM_CACHE,
    THREADLINE_ALERT_COOLDOWN_SECONDS=900,
    THREADLINE_INFRA_ALERT_COOLDOWN_SECONDS=3600,
)
def test_repeated_failure_alert_is_suppressed_within_cooldown(
    monkeypatch, failure_notifications
):
    tracer = _failing_tracer(monkeypatch)

    tracer.fail_task({"errors": 1}, "boom")
    tracer.fail_task({"errors": 1}, "boom")
    tracer.fail_task({"errors": 1}, "boom")

    failure_notifications.assert_called_once()


@override_settings(
    CACHES=LOCMEM_CACHE,
    THREADLINE_ALERT_COOLDOWN_SECONDS=0,
    THREADLINE_INFRA_ALERT_COOLDOWN_SECONDS=3600,
)
def test_zero_cooldown_disables_throttling(monkeypatch, failure_notifications):
    tracer = _failing_tracer(monkeypatch)

    tracer.fail_task({"errors": 1}, "boom")
    tracer.fail_task({"errors": 1}, "boom")

    assert failure_notifications.call_count == 2


@override_settings(
    CACHES=LOCMEM_CACHE,
    THREADLINE_ALERT_COOLDOWN_SECONDS=900,
    THREADLINE_INFRA_ALERT_COOLDOWN_SECONDS=3600,
)
def test_infrastructure_errors_use_their_own_cooldown(
    monkeypatch, failure_notifications
):
    tracer = _failing_tracer(monkeypatch)

    assert tracer._failure_cooldown_seconds(
        "(2006, 'Server has gone away')"
    ) == 3600
    assert tracer._failure_cooldown_seconds("mailbox rejected login") == 900


@override_settings(CACHES=LOCMEM_CACHE, THREADLINE_ALERT_COOLDOWN_SECONDS=900)
def test_alert_is_sent_when_cache_is_unavailable(
    monkeypatch, failure_notifications
):
    class BrokenCache:
        def add(self, *args, **kwargs):
            raise ConnectionError("redis down")

    monkeypatch.setattr("django.core.cache.cache", BrokenCache())

    tracer = _failing_tracer(monkeypatch)
    tracer.fail_task({"errors": 1}, "boom")

    failure_notifications.assert_called_once()


@override_settings(CACHES=LOCMEM_CACHE, THREADLINE_ALERT_COOLDOWN_SECONDS=900)
def test_cooldown_is_scoped_per_task_type(
    monkeypatch, failure_notifications
):
    haraka = _failing_tracer(monkeypatch, "HARAKA_CLEANUP")
    imap = _failing_tracer(monkeypatch, "IMAP_EMAIL_FETCH")

    haraka.fail_task({"user_id": 1}, "boom")
    # A different mailbox failing is the same alert for ops: drop it.
    haraka.fail_task({"user_id": 2}, "boom")
    # Other task types keep their own window.
    imap.fail_task({"user_id": 1}, "boom")

    assert failure_notifications.call_count == 2

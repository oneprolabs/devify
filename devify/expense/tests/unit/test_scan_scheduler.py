"""Unit tests for the scan schedule to Beat synchronization."""

import pytest
from django_celery_beat.models import PeriodicTask

from expense.constants import (
    DEFAULT_SCAN_SCHEDULE,
    SCAN_TASK_NAME,
    SCAN_TASK_PATH,
)
from expense.services.config_service import get_app_config
from expense.services.scan_scheduler import sync_scan_periodic_task


pytestmark = [pytest.mark.unit, pytest.mark.django_db]


class TestScanScheduler:
    def test_sync_creates_beat_entry_with_default_schedule(self):
        result = sync_scan_periodic_task()

        task = PeriodicTask.objects.get(name=SCAN_TASK_NAME)
        assert result["enabled"] is True
        assert result["schedule"] == DEFAULT_SCAN_SCHEDULE
        assert task.task == SCAN_TASK_PATH
        assert task.enabled is True

    def test_task_stays_on_the_default_queue(self):
        # The worker runs without -Q, so a named queue would park the task
        # where nothing consumes it.
        sync_scan_periodic_task()

        assert PeriodicTask.objects.get(name=SCAN_TASK_NAME).queue is None

    def test_changing_the_cron_updates_beat(self):
        sync_scan_periodic_task()
        config = get_app_config()
        config.scan_schedule = "30 6 * * 1"
        config.save(update_fields=["scan_schedule"])

        sync_scan_periodic_task(config)

        crontab = PeriodicTask.objects.get(name=SCAN_TASK_NAME).crontab
        assert crontab.minute == "30"
        assert crontab.hour == "6"
        assert crontab.day_of_week == "1"

    def test_deactivating_the_app_removes_the_beat_entry(self):
        sync_scan_periodic_task()
        config = get_app_config()
        config.is_active = False
        config.save(update_fields=["is_active"])

        result = sync_scan_periodic_task(config)

        assert result["enabled"] is False
        assert not PeriodicTask.objects.filter(name=SCAN_TASK_NAME).exists()

    def test_blank_schedule_falls_back_to_the_default(self):
        config = get_app_config()
        config.scan_schedule = "   "
        config.save(update_fields=["scan_schedule"])

        result = sync_scan_periodic_task(config)

        assert result["schedule"] == DEFAULT_SCAN_SCHEDULE

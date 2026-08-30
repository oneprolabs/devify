"""Keep the Celery Beat entry in sync with the configured scan schedule."""

from __future__ import annotations

from billing.services.periodic_task_scheduler import sync_cron_periodic_task
from expense.constants import (
    DEFAULT_SCAN_SCHEDULE,
    SCAN_SCHEDULE_ERROR,
    SCAN_TASK_NAME,
    SCAN_TASK_PATH,
)


def sync_scan_periodic_task(config=None) -> dict:
    """
    Write the scan schedule into django_celery_beat.

    Called after the admin config changes so a new cron takes effect without
    a redeploy.
    """
    from expense.services.config_service import get_app_config

    config = config or get_app_config()
    schedule = (config.scan_schedule or "").strip() or DEFAULT_SCAN_SCHEDULE
    enabled = bool(config.is_active)

    created, task_id = sync_cron_periodic_task(
        task_name=SCAN_TASK_NAME,
        task_path=SCAN_TASK_PATH,
        enabled=enabled,
        schedule=schedule if enabled else "",
        task_kwargs={},
        error_message=SCAN_SCHEDULE_ERROR,
        # The worker starts without -Q, so it only consumes the default
        # queue. Naming a dedicated queue here would park the task where
        # nothing picks it up.
        queue=None,
    )
    return {
        "created": created,
        "enabled": enabled,
        "schedule": schedule if enabled else "",
        "task_id": task_id,
    }

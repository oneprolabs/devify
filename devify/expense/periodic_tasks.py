"""
Register Expense periodic tasks with the project registry.

The registry seeds the Beat row on first boot; afterwards the admin config
API owns the schedule through ``sync_scan_periodic_task``.
"""

from celery.schedules import crontab

from core.periodic_registry import TASK_REGISTRY
from expense.constants import (
    DEFAULT_SCAN_SCHEDULE,
    SCAN_TASK_NAME,
    SCAN_TASK_PATH,
)


def _default_crontab() -> crontab:
    minute, hour, day_of_month, month_of_year, day_of_week = (
        DEFAULT_SCAN_SCHEDULE.split()
    )
    return crontab(
        minute=minute,
        hour=hour,
        day_of_month=day_of_month,
        month_of_year=month_of_year,
        day_of_week=day_of_week,
    )


def register_periodic_tasks():
    TASK_REGISTRY.add(
        name=SCAN_TASK_NAME,
        task=SCAN_TASK_PATH,
        schedule=_default_crontab(),
    )

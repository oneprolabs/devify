"""Expense scheduling tasks."""

from __future__ import annotations

import logging

from celery import shared_task

from expense.models import ExpenseUserConfig, InvoiceScanRun
from expense.services.config_service import get_app_config
from expense.services.scanner import start_scan

logger = logging.getLogger(__name__)


@shared_task
def schedule_invoice_scan() -> dict:
    """Fan out one scan per enabled user."""
    config = get_app_config()
    if not config.is_active:
        logger.info("Expense app is inactive, skipping scan dispatch")
        return {"dispatched": 0, "skipped_reason": "app_inactive"}

    configs = ExpenseUserConfig.objects.filter(enabled=True).select_related(
        "user"
    )

    dispatched = 0
    for user_config in configs:
        try:
            start_scan(
                user_config.user,
                trigger=InvoiceScanRun.Trigger.SCHEDULED,
            )
            dispatched += 1
        except Exception:
            # One user's failure must not stop the rest of the fan-out.
            logger.exception(
                "Failed to start expense scan for user %s",
                user_config.user_id,
            )

    logger.info("Expense scan dispatched for %s users", dispatched)
    return {"dispatched": dispatched}

"""Expense scheduling tasks."""

from __future__ import annotations

import logging

from celery import shared_task

from expense.models import ExpenseUserConfig
from expense.services.config_service import get_app_config

logger = logging.getLogger(__name__)


@shared_task
def schedule_invoice_scan() -> dict:
    """
    Fan out one scan task per enabled user.

    M1 only resolves the audience and reports it; the per-user scan lands in
    M2, so this deliberately does not queue any work or consume credits yet.
    """
    config = get_app_config()
    if not config.is_active:
        logger.info("Expense app is inactive, skipping scan dispatch")
        return {"dispatched": 0, "skipped_reason": "app_inactive"}

    user_ids = list(
        ExpenseUserConfig.objects.filter(enabled=True).values_list(
            "user_id", flat=True
        )
    )
    logger.info(
        "Expense scan dispatch resolved %s enabled users", len(user_ids)
    )
    return {"dispatched": 0, "enabled_users": len(user_ids)}

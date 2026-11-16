"""
Startup recovery helpers for Threadline email processing.

These helpers run when a Celery worker becomes ready. They recover stale
processing records that were likely left behind by a worker crash or restart.
"""

from __future__ import annotations

import logging
from datetime import timedelta

from agentcore_task.adapters.django import acquire_task_lock, release_task_lock
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from threadline.models import EmailMessage
from threadline.services.processing_control import paused_user_ids
from threadline.services.workflow_recovery import (
    expire_workflow_reservation,
    workflows_in_flight,
)
from threadline.state_machine import EmailStatus
from threadline.tasks.email_merge import process_email_merge

logger = logging.getLogger(__name__)


STARTUP_RECOVERY_LOCK_NAME = "threadline_startup_recovery"


def recover_stuck_processing_emails(
    *,
    timeout_minutes: int | None = None,
) -> dict:
    """
    Requeue stale processing emails after a worker restart.

    The recovery is intentionally conservative:
    - Only EmailMessage rows in PROCESSING state are considered.
    - Only rows older than the timeout window are recovered.
    - A distributed lock ensures only one worker performs recovery.

    Returns:
        dict: Recovery statistics.
    """
    timeout_minutes = timeout_minutes or settings.TASK_TIMEOUT_MINUTES
    lock_timeout = max(timeout_minutes, 5) * 60

    if not acquire_task_lock(
        STARTUP_RECOVERY_LOCK_NAME,
        timeout=lock_timeout,
    ):
        logger.info(
            "Skipping startup recovery because another worker holds the lock"
        )
        return {
            "status": "skipped",
            "reason": "startup_recovery_lock_exists",
            "timeout_minutes": timeout_minutes,
            "requeued_count": 0,
            "candidate_count": 0,
        }

    try:
        now = timezone.now()
        timeout_threshold = now - timedelta(minutes=timeout_minutes)

        candidates = EmailMessage.objects.filter(
            status=EmailStatus.PROCESSING.value,
            updated_at__lt=timeout_threshold,
        ).exclude(user_id__in=paused_user_ids())
        floor_hours = getattr(settings, "STUCK_EMAIL_MAX_AGE_HOURS", 48)
        if floor_hours:
            candidates = candidates.filter(
                updated_at__gte=now - timedelta(hours=floor_hours)
            )
        candidates = list(candidates.order_by("updated_at", "id"))
        in_flight = workflows_in_flight() if candidates else set()
        if in_flight is None:
            return {
                "status": "skipped", "reason": "inspection_unavailable",
                "timeout_minutes": timeout_minutes,
                "candidate_count": len(candidates), "requeued_count": 0,
            }

        requeued_count = 0
        dispatch_errors = []

        for email in candidates:
            if str(email.pk) in in_flight:
                continue
            try:
                # Re-open only the row inspected above. A queued/running
                # request or concurrent completion must never be overwritten.
                with transaction.atomic():
                    if not EmailMessage.objects.filter(
                        pk=email.pk, status=EmailStatus.PROCESSING.value,
                        updated_at=email.updated_at,
                    ).update(status=EmailStatus.FAILED.value, updated_at=now):
                        continue
                    expire_workflow_reservation(email.pk)
                process_email_merge.delay(
                    str(email.id),
                    force=False,
                    trigger_source="retry_task",
                )
                requeued_count += 1
                logger.info(
                    "Recovered stale processing email %s (%s) "
                    "trigger_source=retry_task",
                    email.id,
                    email.uuid,
                )
            except Exception as exc:
                logger.exception(
                    "Failed to requeue stale processing email %s: %s",
                    email.id,
                    exc,
                )
                dispatch_errors.append(
                    {
                        "email_id": str(email.id),
                        "uuid": str(email.uuid),
                        "error": str(exc),
                    }
                )

        return {
            "status": "success",
            "timeout_minutes": timeout_minutes,
            "timeout_threshold": timeout_threshold.isoformat(),
            "candidate_count": len(candidates),
            "requeued_count": requeued_count,
            "dispatch_errors": dispatch_errors,
        }

    finally:
        release_task_lock(STARTUP_RECOVERY_LOCK_NAME)

import logging
import os

from celery.signals import worker_ready

logger = logging.getLogger(__name__)


@worker_ready.connect(dispatch_uid="threadline.startup_recovery")
def recover_processing_emails_on_worker_ready(sender=None, **kwargs):
    """
    Requeue stale processing emails when a Celery worker becomes ready.

    This module is intentionally named as a Celery bootstrap hook so other
    apps can follow the same pattern for their own worker startup logic.
    """
    if os.getenv("CHAT_DEDICATED_WORKER", "").lower() in {"1", "true", "yes"}:
        return
    try:
        logger.info("Threadline worker_ready signal received")
        from threadline.tasks.scheduler import (
            recover_email_workflows_after_startup,
        )

        task = recover_email_workflows_after_startup.apply_async(countdown=10)
        logger.info(
            "Queued Threadline startup recovery: %s", task.id,
        )
    except Exception as exc:
        logger.exception(
            "Threadline startup recovery failed on worker ready: %s", exc
        )

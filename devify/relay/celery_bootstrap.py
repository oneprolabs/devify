"""Relay Celery startup hooks."""

from __future__ import annotations

import logging
import os

from celery.signals import worker_ready

logger = logging.getLogger(__name__)


@worker_ready.connect(dispatch_uid="relay.legacy_issue_config_sync")
def sync_legacy_issue_config_on_worker_ready(sender=None, **kwargs):
    """Run the one-time legacy config sync when a worker becomes ready."""
    if os.getenv("CHAT_DEDICATED_WORKER", "").lower() in {"1", "true", "yes"}:
        return
    try:
        logger.info("Relay worker_ready signal received")
        from relay.services.legacy_sync import sync_all_legacy_issue_configs

        result = sync_all_legacy_issue_configs()
        logger.info("Relay legacy sync completed: %s", result)
    except Exception as exc:
        logger.exception("Relay legacy sync failed on worker ready: %s", exc)

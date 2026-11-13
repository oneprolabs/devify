"""Worker startup checks for the chat analysis engine."""

import logging
import os

from celery.signals import worker_ready

logger = logging.getLogger(__name__)


@worker_ready.connect(dispatch_uid="chat_ingestion.startup_recovery")
def recover_chat_uploads_on_worker_ready(sender=None, **kwargs):
    """Recover stale uploads after a worker restart."""
    try:
        from chat_ingestion.recovery import recover_stale_uploads

        logger.info("Chat upload recovery: %s", recover_stale_uploads())
    except Exception:
        logger.exception("Chat upload startup recovery failed")


@worker_ready.connect(dispatch_uid="chat_analysis.engine_freshness")
def warn_when_analysis_code_is_stale(sender=None, **kwargs):
    """Warn when analysis code was edited after this worker imported it.

    A worker keeps the module it imported at startup. Editing
    ``chat_analysis.execution`` without restarting the worker silently
    produces data from the old engine, which is how events ended up without
    activity windows in development.
    """
    try:
        from chat_analysis import execution

        modified_at = os.path.getmtime(execution.MODULE_PATH)
        if modified_at > execution.MODULE_LOADED_AT + 1:
            logger.error(
                "chat_analysis code changed after this worker started "
                "(loaded=%s, modified=%s). Restart the worker before running "
                "analysis jobs; engine=%s.",
                execution.MODULE_LOADED_AT,
                modified_at,
                execution.ENGINE_VERSION,
            )
        else:
            logger.info(
                "chat_analysis engine ready: %s", execution.ENGINE_VERSION
            )
    except Exception:
        logger.exception("chat_analysis freshness check failed")

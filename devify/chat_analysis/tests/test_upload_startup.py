from unittest.mock import patch

from chat_analysis.celery_bootstrap import recover_chat_uploads_on_worker_ready


def test_worker_start_runs_upload_recovery():
    with patch("chat_ingestion.recovery.recover_stale_uploads") as recover:
        recover_chat_uploads_on_worker_ready()
    recover.assert_called_once_with()


def test_worker_start_survives_recovery_failure():
    with patch(
        "chat_ingestion.recovery.recover_stale_uploads",
        side_effect=RuntimeError("storage unavailable"),
    ):
        recover_chat_uploads_on_worker_ready()

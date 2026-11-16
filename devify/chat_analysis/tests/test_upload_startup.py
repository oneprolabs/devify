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


def test_dedicated_chat_workers_skip_unrelated_startup_recovery(monkeypatch):
    from relay.celery_bootstrap import sync_legacy_issue_config_on_worker_ready
    from threadline.celery_bootstrap import recover_processing_emails_on_worker_ready

    monkeypatch.setenv("CHAT_DEDICATED_WORKER", "true")
    with patch("threadline.services.startup_recovery.recover_stuck_processing_emails") as email, patch("relay.services.legacy_sync.sync_all_legacy_issue_configs") as relay:
        recover_processing_emails_on_worker_ready()
        sync_legacy_issue_config_on_worker_ready()
    email.assert_not_called()
    relay.assert_not_called()


def test_default_worker_keeps_existing_startup_recovery(monkeypatch):
    from relay.celery_bootstrap import sync_legacy_issue_config_on_worker_ready
    from threadline.celery_bootstrap import recover_processing_emails_on_worker_ready

    monkeypatch.delenv("CHAT_DEDICATED_WORKER", raising=False)
    with patch("threadline.services.startup_recovery.recover_stuck_processing_emails") as email, patch("relay.services.legacy_sync.sync_all_legacy_issue_configs") as relay:
        recover_processing_emails_on_worker_ready()
        sync_legacy_issue_config_on_worker_ready()
    email.assert_called_once_with()
    relay.assert_called_once_with()

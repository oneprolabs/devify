import hashlib
import threading
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.contrib.auth.models import User
from django.db import close_old_connections, connection, transaction
from django.utils import timezone

from chat_ingestion.models import UploadBatch
from chat_ingestion.recovery import recover_stale_uploads
from chat_ingestion.services import archive_path
from spaces.models import Space

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture(autouse=True)
def isolated_archives(settings, tmp_path):
    settings.CHAT_UPLOAD_ARCHIVE_DIR = str(tmp_path / "archives")


def make_batch(key, status=UploadBatch.Status.PROCESSING):
    owner = User.objects.create_user(username=f"owner-{key}")
    space = Space.objects.get(personal_owner=owner)
    batch = UploadBatch.objects.create(
        space=space,
        uploaded_by=owner,
        source_type="wechat",
        idempotency_key=key,
        status=status,
    )
    UploadBatch.objects.filter(pk=batch.pk).update(
        updated_at=timezone.now() - timedelta(minutes=30)
    )
    return batch


def write_archive(batch, content=b"valid archive"):
    path = archive_path(batch)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    UploadBatch.objects.filter(pk=batch.pk).update(
        archive_sha256=hashlib.sha256(content).hexdigest(),
        archive_size=len(content),
    )


def test_recovery_requeues_verified_batch_only_once():
    batch = make_batch("good")
    write_archive(batch)
    with patch("chat_ingestion.tasks.dispatch_parse_chat_upload") as dispatch:
        assert recover_stale_uploads() == {
            "requeued": 1,
            "missing_or_invalid": 0,
        }
        assert recover_stale_uploads() == {
            "requeued": 0,
            "missing_or_invalid": 0,
        }
    assert dispatch.call_count == 1
    assert dispatch.call_args.args[0].pk == batch.pk
    batch.refresh_from_db()
    assert batch.status == UploadBatch.Status.PROCESSING


@pytest.mark.parametrize("corrupt", [False, True])
def test_recovery_fails_missing_or_corrupt_archive_without_dispatch(corrupt):
    batch = make_batch("invalid")
    if corrupt:
        write_archive(batch)
        archive_path(batch).write_bytes(b"wrong archive")
    with patch("chat_ingestion.tasks.dispatch_parse_chat_upload") as dispatch:
        assert recover_stale_uploads() == {
            "requeued": 0,
            "missing_or_invalid": 1,
        }
    dispatch.assert_not_called()
    batch.refresh_from_db()
    assert batch.status == UploadBatch.Status.FAILED
    assert "共享存储" in batch.error_message


def test_recovery_leaves_uploading_and_recent_batches_alone():
    uploading = make_batch("uploading", UploadBatch.Status.UPLOADING)
    recent = make_batch("recent")
    recent.save(update_fields=("updated_at",))
    with patch("chat_ingestion.tasks.dispatch_parse_chat_upload") as dispatch:
        assert recover_stale_uploads() == {
            "requeued": 0,
            "missing_or_invalid": 0,
        }
    dispatch.assert_not_called()
    uploading.refresh_from_db()
    assert uploading.status == UploadBatch.Status.UPLOADING


def test_recovery_does_not_fail_when_storage_is_temporarily_unreadable():
    batch = make_batch("storage-unavailable")
    write_archive(batch)
    with (
        patch("chat_ingestion.recovery.archive_path") as path,
        patch("chat_ingestion.tasks.dispatch_parse_chat_upload") as dispatch,
    ):
        path.return_value.stat.side_effect = PermissionError("unavailable")
        assert recover_stale_uploads() == {
            "requeued": 0,
            "missing_or_invalid": 0,
        }
    dispatch.assert_not_called()
    batch.refresh_from_db()
    assert batch.status == UploadBatch.Status.PROCESSING


def test_recovery_skips_a_batch_locked_by_an_active_parser():
    if not connection.features.has_select_for_update_skip_locked:
        pytest.skip("Database does not support skip_locked")
    batch = make_batch("locked")
    write_archive(batch)
    locked = threading.Event()
    release = threading.Event()

    def hold_lock():
        close_old_connections()
        try:
            with transaction.atomic():
                UploadBatch.objects.select_for_update().get(pk=batch.pk)
                locked.set()
                assert release.wait(10)
        finally:
            close_old_connections()

    thread = threading.Thread(target=hold_lock)
    thread.start()
    try:
        assert locked.wait(10)
        with patch(
            "chat_ingestion.tasks.dispatch_parse_chat_upload"
        ) as dispatch:
            assert recover_stale_uploads() == {
                "requeued": 0,
                "missing_or_invalid": 0,
            }
            dispatch.assert_not_called()
    finally:
        release.set()
        thread.join(timeout=10)
    assert not thread.is_alive()


def test_recovery_is_registered_for_periodic_execution():
    from chat_analysis.periodic_tasks import register_periodic_tasks

    with patch("chat_analysis.periodic_tasks.TASK_REGISTRY") as registry:
        register_periodic_tasks()
    assert any(
        call.kwargs.get("task")
        == "chat_ingestion.tasks.recover_stale_uploads_task"
        for call in registry.add.call_args_list
    )

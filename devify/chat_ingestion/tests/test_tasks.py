from unittest.mock import patch

import pytest
from celery.exceptions import Retry, SoftTimeLimitExceeded
from django.contrib.auth.models import User

from chat_ingestion.models import UploadBatch
from chat_ingestion.tasks import parse_chat_upload_task
from spaces.models import Space, SpaceMembership

pytestmark = pytest.mark.django_db


def make_batch(owner, slug="task-team"):
    space = Space.objects.create(
        name=slug,
        slug=slug,
        kind=Space.Kind.TEAM,
        owner=owner,
    )
    SpaceMembership.objects.create(
        space=space,
        user=owner,
        role=SpaceMembership.Role.OWNER,
    )
    return UploadBatch.objects.create(
        space=space,
        uploaded_by=owner,
        source_type=UploadBatch.SourceType.WECHAT,
        idempotency_key=f"{slug}-batch",
        status=UploadBatch.Status.PROCESSING,
    )


def test_parser_task_skips_non_processing_batches():
    owner = User.objects.create_user(username="task-skip-owner")
    batch = make_batch(owner, "task-skip-team")
    batch.status = UploadBatch.Status.COMPLETED
    batch.save(update_fields=("status", "updated_at"))

    result = parse_chat_upload_task.run(batch.pk)

    assert result == {
        "batch_id": batch.pk,
        "status": UploadBatch.Status.COMPLETED,
    }


def test_parser_task_rejects_batch_after_uploader_loses_membership():
    owner = User.objects.create_user(username="task-removed-owner")
    batch = make_batch(owner, "task-removed-team")
    membership = SpaceMembership.objects.get(space=batch.space, user=owner)
    membership.status = SpaceMembership.Status.REMOVED
    membership.save(update_fields=("status", "updated_at"))

    result = parse_chat_upload_task.run(batch.pk)
    batch.refresh_from_db()

    assert result["status"] == UploadBatch.Status.FAILED
    assert batch.error_message


def test_parser_task_retries_transient_parser_errors():
    owner = User.objects.create_user(username="task-retry-owner")
    batch = make_batch(owner, "task-retry-team")
    with (
        patch(
            "chat_ingestion.tasks.parse_archive",
            side_effect=RuntimeError("temporary filesystem error"),
        ),
        patch.object(
            parse_chat_upload_task,
            "retry",
            side_effect=Retry(),
        ) as retry,
    ):
        with pytest.raises(Retry):
            parse_chat_upload_task.run(batch.pk)

    retry.assert_called_once()


def test_parser_task_marks_timeout_failed():
    owner = User.objects.create_user(username="task-timeout-owner")
    batch = make_batch(owner, "task-timeout-team")
    with patch(
        "chat_ingestion.tasks.parse_archive",
        side_effect=SoftTimeLimitExceeded(),
    ):
        result = parse_chat_upload_task.run(batch.pk)
    batch.refresh_from_db()
    assert result["status"] == UploadBatch.Status.FAILED
    assert batch.status == UploadBatch.Status.FAILED
    assert "time limit" in batch.error_message


def test_completed_batch_recovers_missing_analysis_once():
    from chat_analysis.models import AnalysisJob
    from chat_domain.models import Conversation, Message, MessageOrigin
    from chat_ingestion.models import UploadItem

    owner = User.objects.create_user(username="task-recover-owner")
    batch = make_batch(owner, "task-recover-team")
    batch.status = UploadBatch.Status.COMPLETED
    batch.message_count = 1
    batch.save(update_fields=("status", "message_count", "updated_at"))
    conversation = Conversation.objects.create(
        space=batch.space,
        platform="wechat",
        source_namespace="local",
        source_conversation_id="recover",
        identity_key="recover",
    )
    message = Message.objects.create(
        conversation=conversation, message_key="recover", ingest_seq=1
    )
    item = UploadItem.objects.create(batch=batch, path="messages")
    MessageOrigin.objects.create(
        message=message, upload_item=item, locator_key="1", parser_version="1"
    )

    with patch(
        "chat_ingestion.tasks.create_analysis_job",
        side_effect=RuntimeError("temporarily unavailable"),
    ):
        parse_chat_upload_task.run(batch.pk)
    assert not batch.analysis_jobs.exists()
    with patch("chat_ingestion.tasks.execute_analysis_job") as execute:
        parse_chat_upload_task.run(batch.pk)
        parse_chat_upload_task.run(batch.pk)
    assert batch.analysis_jobs.count() == 1
    assert AnalysisJob.objects.filter(upload_batches=batch).count() == 1
    execute.assert_called_once()

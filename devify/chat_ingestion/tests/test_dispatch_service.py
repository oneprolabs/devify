"""Upload dispatch must preserve transaction and inline execution behavior."""

from types import SimpleNamespace
from unittest.mock import Mock, patch

from chat_ingestion.services.dispatch import _enqueue_parse


def make_batch(**values):
    """Build the minimal batch interface used by the dispatcher."""
    return SimpleNamespace(
        pk=42,
        source_id=None,
        source_import_id=None,
        **values,
    )


def test_async_dispatch_waits_for_transaction_commit(settings):
    settings.CHAT_UPLOAD_PARSE_INLINE = False
    batch = make_batch()
    with (
        patch("chat_ingestion.tasks.dispatch_parse_chat_upload") as dispatch,
        patch(
            "chat_ingestion.services.dispatch.transaction.on_commit"
        ) as on_commit,
    ):
        assert _enqueue_parse(batch) is None
        dispatch.assert_not_called()
        on_commit.assert_called_once()
        callback = on_commit.call_args.args[0]
        callback()
        dispatch.assert_called_once_with(batch)


def test_inline_dispatch_returns_task_result_without_commit_hook(settings):
    settings.CHAT_UPLOAD_PARSE_INLINE = True
    batch = make_batch()
    result = {"status": "completed"}
    with (
        patch(
            "chat_ingestion.tasks.parse_chat_upload_task.run",
            return_value=result,
        ) as run,
        patch("chat_ingestion.tasks.dispatch_parse_chat_upload") as dispatch,
        patch(
            "chat_ingestion.services.dispatch.transaction.on_commit"
        ) as on_commit,
    ):
        assert _enqueue_parse(batch) is result
        run.assert_called_once_with(batch.pk)
        dispatch.assert_not_called()
        on_commit.assert_not_called()


def test_missing_source_import_is_recorded_before_dispatch(settings):
    settings.CHAT_UPLOAD_PARSE_INLINE = False
    batch = make_batch(space=object(), source=object(), uploaded_by=object())
    batch.source_id = 7
    batch.save = Mock()
    with (
        patch(
            "chat_ingestion.services.dispatch.SourceImport.objects.create"
        ) as create,
        patch(
            "chat_ingestion.services.dispatch.transaction.on_commit"
        ) as on_commit,
    ):
        _enqueue_parse(batch)
        create.assert_called_once_with(
            space=batch.space,
            source=batch.source,
            initiated_by=batch.uploaded_by,
        )
        assert batch.source_import is create.return_value
        batch.save.assert_called_once_with(
            update_fields=("source_import", "updated_at")
        )
        on_commit.assert_called_once()

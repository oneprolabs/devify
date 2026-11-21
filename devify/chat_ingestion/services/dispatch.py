"""Dispatch services for upload batches."""

from chat_sources.models import SourceImport
from django.conf import settings
from django.db import transaction


def _enqueue_parse(batch):
    if batch.source_id and batch.source_import_id is None:
        batch.source_import = SourceImport.objects.create(
            space=batch.space,
            source=batch.source,
            initiated_by=batch.uploaded_by,
        )
        batch.save(update_fields=("source_import", "updated_at"))

    def dispatch():
        from chat_ingestion.tasks import (
            dispatch_parse_chat_upload,
            parse_chat_upload_task,
        )

        if getattr(settings, "CHAT_UPLOAD_PARSE_INLINE", False):
            return parse_chat_upload_task.run(batch.pk)
        return dispatch_parse_chat_upload(batch)

    if getattr(settings, "CHAT_UPLOAD_PARSE_INLINE", False):
        return dispatch()
    transaction.on_commit(dispatch)
    return None

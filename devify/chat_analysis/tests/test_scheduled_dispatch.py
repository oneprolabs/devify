from datetime import timedelta
from unittest.mock import patch

import pytest
from django.contrib.auth.models import User
from django.utils import timezone

from chat_analysis.models import AnalysisJob, AnalysisJobMessage
from chat_analysis.schedule_window import BEIJING
from chat_analysis.scheduled_dispatch import (
    dispatch_due_analysis,
    schedule_conversation,
)
from chat_analysis.services import add_note_evidence, create_note
from chat_analysis.tests.test_execution import (
    add_message,
    make_conversation,
    make_job,
    make_space,
)
from chat_domain.models import MessageOrigin
from chat_ingestion.models import UploadBatch, UploadItem

pytestmark = pytest.mark.django_db(transaction=True)


def origin(
    message,
    owner,
    space,
    key,
    completed_at,
    status=UploadBatch.Status.COMPLETED,
):
    batch = UploadBatch.objects.create(
        space=space,
        uploaded_by=owner,
        source_type="wechat",
        idempotency_key=key,
        status=status,
        completed_at=completed_at,
    )
    item = UploadItem.objects.create(batch=batch, path=f"{key}.jsonl")
    MessageOrigin.objects.create(
        message=message, upload_item=item, locator_key=key, parser_version="v1"
    )
    return batch


def test_snapshot_excludes_incomplete_and_future_batches_and_deduplicates():
    owner = User.objects.create_user(username="scheduled-dispatch-owner")
    space = make_space(owner, "scheduled-dispatch-space")
    conversation = make_conversation(space)
    first = add_message(conversation, 1)
    second = add_message(conversation, 2)
    third = add_message(conversation, 3)
    boundary = timezone.now() + timedelta(seconds=2)
    origin(first, owner, space, "old", boundary - timedelta(seconds=1))
    origin(first, owner, space, "duplicate", boundary - timedelta(seconds=1))
    origin(second, owner, space, "future", boundary + timedelta(seconds=1))
    origin(
        third, owner, space, "incomplete", None, UploadBatch.Status.PROCESSING
    )
    with patch("chat_analysis.tasks.dispatch_analysis_job") as dispatch:
        job = schedule_conversation(conversation.pk, boundary)
        assert job is not None
        assert list(
            job.scheduled_messages.values_list("message_id", flat=True)
        ) == [first.pk]
        assert schedule_conversation(conversation.pk, boundary) is None
    assert dispatch.call_count == 1
    assert AnalysisJobMessage.objects.count() == 1


def test_due_slot_enqueues_each_ready_conversation_once():
    owner = User.objects.create_user(username="due-slot-owner")
    space = make_space(owner, "due-slot-space")
    conversation = make_conversation(space)
    message = add_message(conversation, 1)
    now = timezone.now()
    local = now.astimezone(BEIJING)
    slot_start = local.replace(second=0, microsecond=0)
    before = slot_start - timedelta(seconds=30)
    origin(message, owner, space, "due-slot", before)
    from chat_domain.models import Message, MessageOrigin
    from chat_ingestion.models import UploadBatch
    Message.objects.filter(pk=message.pk).update(created_at=before)
    MessageOrigin.objects.filter(message=message).update(created_at=before)
    UploadBatch.objects.filter(space=space).update(completed_at=before)
    schedule = f"{slot_start.hour:02d}:{slot_start.minute:02d}"
    with patch(
        "chat_analysis.tasks.dispatch_analysis_job"
    ) as dispatch:
        first = dispatch_due_analysis(now, schedule)
        second = dispatch_due_analysis(now, schedule)
    assert first["jobs"] == 1
    assert second == {"jobs": 0, "slot": first["slot"]}
    dispatch.assert_called_once()


def test_off_slot_does_not_enqueue():
    owner = User.objects.create_user(username="off-slot-owner")
    space = make_space(owner, "off-slot-space")
    conversation = make_conversation(space)
    message = add_message(conversation, 1)
    now = timezone.now()
    origin(message, owner, space, "off-slot", now - timedelta(seconds=1))
    local = now.astimezone(BEIJING)
    other = (local.hour + 1) % 24
    with patch(
        "chat_analysis.tasks.dispatch_analysis_job"
    ) as dispatch:
        result = dispatch_due_analysis(now, f"{other:02d}:00")
    assert result["jobs"] == 0
    dispatch.assert_not_called()


def test_previously_analyzed_evidence_is_not_scheduled_again():
    owner = User.objects.create_user(username="legacy-scheduled-owner")
    space = make_space(owner, "legacy-scheduled-space")
    conversation = make_conversation(space)
    old = add_message(conversation, 1)
    new = add_message(conversation, 2)
    old_job = make_job(space, owner, conversation, end_seq=1)
    old_job.state = AnalysisJob.State.READY
    old_job.save(update_fields=("state",))
    note = create_note(
        actor=owner,
        space=space,
        note_key="old-note",
        title="old",
        content="old",
        analysis_job=old_job,
    )
    add_note_evidence(actor=owner, note=note, message=old)
    boundary = timezone.now() + timedelta(seconds=2)
    origin(old, owner, space, "old-evidence", boundary - timedelta(seconds=1))
    origin(new, owner, space, "new-evidence", boundary - timedelta(seconds=1))
    with patch("chat_analysis.tasks.dispatch_analysis_job"):
        job = schedule_conversation(conversation.pk, boundary)
    assert list(
        job.scheduled_messages.values_list("message_id", flat=True)
    ) == [new.pk]

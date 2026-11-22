"""History batching, cross-conversation merge, and token windows."""

import json
from datetime import datetime, timedelta
from runpy import run_path
from unittest.mock import patch

import pytest
from django.contrib.auth.models import User
from django.utils import timezone

from chat_analysis import execution
from chat_analysis.models import (
    AnalysisJob,
    AnalysisJobMessage,
    Event,
    EventEvidence,
    Note,
    NoteEvidence,
)
from chat_analysis.scheduled_dispatch import (
    LEGACY_OVERSIZE_ERROR,
    schedule_conversation,
)
from chat_analysis.tests.test_event_extraction import fake_llm
from chat_analysis.tests.test_execution import (
    add_message,
    make_conversation,
    make_job,
    make_space,
)
from chat_analysis.tests.test_scheduled_dispatch import origin
from chat_analysis.token_budget import MessageExceedsBudget
from chat_domain.models import Conversation, Message, MessageOrigin
from chat_ingestion.models import UploadBatch
from chat_ingestion.views import _analysis_summaries
from core.settings import celery as celery_settings

pytestmark = pytest.mark.django_db(transaction=True)


def _backdate(message, when):
    Message.objects.filter(pk=message.pk).update(created_at=when)
    MessageOrigin.objects.filter(message=message).update(created_at=when)
    UploadBatch.objects.filter(
        items__chat_message_origins__message=message
    ).update(completed_at=when)


def _store(message, owner, space, key, when):
    origin(message, owner, space, key, when)
    _backdate(message, when)
    return message


def _group(space, key):
    conversation = make_conversation(space, key)
    conversation.kind = Conversation.Kind.GROUP
    conversation.save(update_fields=("kind",))
    return conversation


def test_large_history_is_capped_and_does_not_block_other_conversations(
    monkeypatch,
):
    monkeypatch.setattr(
        "chat_analysis.scheduled_dispatch.MAX_MESSAGES_PER_JOB", 2
    )
    owner = User.objects.create_user(username="history-cap-owner")
    space = make_space(owner, "history-cap-space")
    busy = _group(space, "history-busy")
    other = _group(space, "history-other")
    boundary = timezone.now() + timedelta(seconds=5)
    stored = boundary - timedelta(seconds=2)
    for index in range(1, 5):
        _store(
            add_message(busy, index, text=f"历史记录 {index}"),
            owner,
            space,
            f"history-cap-{index}",
            stored,
        )
    other_message = _store(
        add_message(other, 1, text="另一会话"),
        owner,
        space,
        "history-cap-other",
        stored,
    )

    with patch("chat_analysis.tasks.dispatch_analysis_job"):
        first = schedule_conversation(busy.pk, boundary)
        parallel = schedule_conversation(other.pk, boundary)
        blocked = schedule_conversation(busy.pk, boundary)
        first.state = AnalysisJob.State.READY
        first.save(update_fields=("state", "updated_at"))
        first.scheduled_messages.update(completed_at=timezone.now())
        second = schedule_conversation(busy.pk, boundary)

    assert [
        item.message.ingest_seq
        for item in first.scheduled_messages.select_related(
            "message"
        ).order_by("message__ingest_seq")
    ] == [1, 2]
    assert list(
        parallel.scheduled_messages.values_list("message_id", flat=True)
    ) == [other_message.pk]
    assert blocked is None
    assert second.pk != first.pk
    assert [
        item.message.ingest_seq
        for item in second.scheduled_messages.select_related(
            "message"
        ).order_by("message__ingest_seq")
    ] == [3, 4]


def test_partial_history_resumes_without_taking_messages_twice(monkeypatch):
    monkeypatch.setattr(
        "chat_analysis.scheduled_dispatch.MAX_MESSAGES_PER_JOB", 2
    )
    owner = User.objects.create_user(username="history-resume-owner")
    space = make_space(owner, "history-resume-space")
    conversation = _group(space, "history-resume")
    other = _group(space, "history-resume-other")
    boundary = timezone.now() + timedelta(seconds=5)
    stored = boundary - timedelta(seconds=2)
    messages = [
        _store(
            add_message(conversation, index, text=f"续跑 {index}"),
            owner,
            space,
            f"history-resume-{index}",
            stored,
        )
        for index in (1, 2, 3)
    ]
    late = add_message(conversation, 4, text="边界之后")
    origin(
        late,
        owner,
        space,
        "history-resume-late",
        boundary + timedelta(seconds=1),
    )
    Message.objects.filter(pk=late.pk).update(
        created_at=boundary + timedelta(seconds=1)
    )
    other_message = _store(
        add_message(other, 1, text="不受阻塞"),
        owner,
        space,
        "history-resume-other",
        stored,
    )

    with patch("chat_analysis.tasks.dispatch_analysis_job"):
        job = schedule_conversation(conversation.pk, boundary)
        job.state = AnalysisJob.State.PARTIAL
        job.save(update_fields=("state", "updated_at"))
        done = AnalysisJobMessage.objects.get(job=job, message=messages[0])
        pending = AnalysisJobMessage.objects.get(job=job, message=messages[1])
        done.completed_at = timezone.now()
        done.save(update_fields=("completed_at",))
        resumed = schedule_conversation(conversation.pk, boundary)
        parallel = schedule_conversation(other.pk, boundary)
        assert schedule_conversation(conversation.pk, boundary) is None
        resumed.state = AnalysisJob.State.READY
        resumed.save(update_fields=("state", "updated_at"))
        resumed.scheduled_messages.update(completed_at=timezone.now())
        follow = schedule_conversation(conversation.pk, boundary)

    assert resumed.pk == job.pk
    pending.refresh_from_db()
    assert pending.completed_at is not None
    assert list(
        parallel.scheduled_messages.values_list("message_id", flat=True)
    ) == [other_message.pk]
    assert list(
        follow.scheduled_messages.values_list("message__ingest_seq", flat=True)
    ) == [3]
    assert not follow.scheduled_messages.filter(message=late).exists()


def test_two_batches_share_one_analysis_and_old_send_time_still_qualifies():
    owner = User.objects.create_user(username="history-merge-owner")
    space = make_space(owner, "history-merge-space")
    conversation = _group(space, "history-merge")
    boundary = timezone.now() + timedelta(seconds=5)
    stored = boundary - timedelta(seconds=2)
    first = add_message(
        conversation,
        1,
        text="几天前的故障",
        occurred_at=stored - timedelta(days=4),
    )
    second = add_message(conversation, 2, text="同一批后续")
    _store(first, owner, space, "history-merge-a", stored)
    _store(second, owner, space, "history-merge-b", stored)
    with patch("chat_analysis.tasks.dispatch_analysis_job") as dispatch:
        job = schedule_conversation(conversation.pk, boundary)
        assert schedule_conversation(conversation.pk, boundary) is None
    assert sorted(
        job.scheduled_messages.values_list("message__ingest_seq", flat=True)
    ) == [1, 2]
    dispatch.assert_called_once()


def test_model_failure_keeps_the_assigned_message_unfinished(
    monkeypatch, settings
):
    settings.CHAT_ANALYSIS_LLM_ENABLED = True
    owner = User.objects.create_user(username="history-fail-owner")
    space = make_space(owner, "history-fail-space")
    conversation = _group(space, "history-fail")
    boundary = timezone.now() + timedelta(seconds=5)
    message = _store(
        add_message(conversation, 1, text="需要分析"),
        owner,
        space,
        "history-fail",
        boundary - timedelta(seconds=2),
    )
    with patch("chat_analysis.tasks.dispatch_analysis_job"):
        job = schedule_conversation(conversation.pk, boundary)

    def fail(_job, _messages, *_results):
        raise RuntimeError("model timeout")

    monkeypatch.setattr(
        "chat_analysis.execution._prepare_chunk", lambda *_args: (None, None)
    )
    monkeypatch.setattr("chat_analysis.execution._write_chunk_note", fail)
    result = execution.execute_analysis_job(job.pk, worker_id="history-fail")
    assignment = AnalysisJobMessage.objects.get(job=job, message=message)
    assert result.job.state == AnalysisJob.State.QUEUED
    assert "RuntimeError: model timeout" in result.job.error
    assert assignment.completed_at is None


@pytest.mark.parametrize("legacy_skip", [False, True])
def test_oversize_message_resumes_with_original_evidence(
    monkeypatch, settings, legacy_skip
):
    settings.CHAT_ANALYSIS_LLM_ENABLED = True
    settings.CHAT_ANALYSIS_MODEL_INPUT_TOKENS = 10000
    settings.CHAT_ANALYSIS_AUTO_CREATE_EVENTS = True
    owner = User.objects.create_user(username="history-oversize-owner")
    space = make_space(owner, "history-oversize-space")
    conversation = _group(space, "history-oversize")
    body = "段落 😀\n" * 3500 + "结尾"
    first = add_message(conversation, 1, text=body)
    second = add_message(conversation, 2, text="后续")
    job = make_job(space, owner, conversation, end_seq=2, key="oversize-job")
    job.specification["scheduled_message_scope"] = True
    job.save(update_fields=("specification",))
    AnalysisJobMessage.objects.create(job=job, message=first)
    AnalysisJobMessage.objects.create(job=job, message=second)
    if legacy_skip:
        job.scheduled_messages.filter(message=first).update(
            error=LEGACY_OVERSIZE_ERROR
        )
        job.scheduled_messages.filter(message=second).update(
            completed_at=timezone.now()
        )
        job.state = AnalysisJob.State.PARTIAL
        job.checkpoint = {
            "last_ingest_seq": 2, "messages_processed": 1, "partial": True,
        }
        job.save(update_fields=("state", "checkpoint"))
        with patch("chat_analysis.tasks.dispatch_analysis_job") as dispatch:
            assert (
                schedule_conversation(conversation.pk, timezone.now()).pk
                == job.pk
            )
            dispatch.assert_called_once()
    seen = []
    interrupted = False

    def llm(*, prompt, content, node_name, **kwargs):
        nonlocal interrupted
        if node_name != "chat_event_extraction":
            return {
                "facts": [],
                "actions": [],
                "risks": [],
                "decisions": [],
            }, {}
        payload = json.loads(content)
        message, = payload["messages"]
        if len(seen) == 1 and not interrupted:
            interrupted = True
            raise TimeoutError
        seen.append((message["seq"], message["text"]))
        events = []
        if message["seq"] == 1:
            prior = payload["open_events_same_conversation"]
            events.append(
                {
                    "action": "attach" if prior else "create",
                    "event_key": prior[0]["event_key"] if prior else "",
                    "title": "跟进故障",
                    "summary": (
                        "需要跟进，已收到结尾"
                        if message["text"].endswith("结尾")
                        else "需要跟进"
                    ),
                    "source_seqs": [1],
                }
            )
        return {"events": events}, {}

    monkeypatch.setattr(execution.LLMTracker, "call_and_track", llm)
    result = execution.execute_analysis_job(job.pk, worker_id="first")
    assert result.job.state == AnalysisJob.State.QUEUED
    assert len(seen) == 1
    assert not job.scheduled_messages.filter(
        message=first, completed_at__isnull=False
    ).exists()
    with patch(
        "django.utils.timezone.now",
        return_value=datetime.fromisoformat(
            result.job.checkpoint["resume_after"],
        ),
    ):
        result = execution.execute_analysis_job(job.pk, worker_id="retry")
    assert result.job.state == AnalysisJob.State.READY
    assert "".join(text for seq, text in seen if seq == 1) == body
    assert [text for seq, text in seen if seq == 2] == (
        [] if legacy_skip else ["后续"]
    )
    assert (
        job.scheduled_messages.filter(completed_at__isnull=False).count() == 2
    )
    assert NoteEvidence.objects.filter(message=first).count() == sum(
        seq == 1 for seq, _ in seen
    )
    fragments = Note.objects.filter(
        analysis_job=job, evidence__message=first
    ).order_by("id")
    assert (
        "".join(
            execution._message_payload(execution._messages_from_note(note))[0][
                "text"
            ]
            for note in fragments
        )
        == body
    )
    event = Event.objects.get(space=space)
    assert event.content == "需要跟进，已收到结尾"
    assert list(event.evidence.values_list("message_id", flat=True)) == [
        first.pk
    ]


def test_across_chats_same_matter_attaches_and_other_matters_stay_separate(
    monkeypatch, settings
):
    settings.CHAT_ANALYSIS_LLM_ENABLED = True
    settings.CHAT_ANALYSIS_AUTO_CREATE_EVENTS = True
    owner = User.objects.create_user(username="cross-chat-owner")
    space = make_space(owner, "cross-chat-space")
    sales = _group(space, "cross-sales")
    ops = _group(space, "cross-ops")
    weekend = _group(space, "cross-weekend")
    sales_message = add_message(sales, 1, text="客户订单库连不上")
    ops_message = add_message(ops, 1, text="订单库连接池耗尽，服务已重启")
    weekend_message = add_message(weekend, 1, text="周日中午聚餐")
    sales_job = make_job(space, owner, sales, end_seq=1, key="cross-sales-job")
    ops_job = make_job(space, owner, ops, end_seq=1, key="cross-ops-job")
    weekend_job = make_job(
        space, owner, weekend, end_seq=1, key="cross-weekend-job"
    )

    def run(job, events):
        monkeypatch.setattr(
            execution.LLMTracker,
            "call_and_track",
            fake_llm(events, []),
        )
        execution.execute_analysis_job(job.pk, worker_id=f"cross-{job.pk}")

    run(
        sales_job,
        [
            {
                "action": "create",
                "event_key": "order-db-outage",
                "title": "订单库连接故障",
                "summary": "客户订单库无法连接。",
                "status": "in_progress",
                "source_seqs": [1],
            }
        ],
    )
    run(
        ops_job,
        [
            {
                "action": "attach",
                "event_key": "order-db-outage",
                "title": "订单库连接故障",
                "summary": "连接池耗尽，服务已重启。",
                "status": "done",
                "source_seqs": [1],
            }
        ],
    )
    run(
        weekend_job,
        [
            {
                "action": "create",
                "event_key": "sunday-lunch",
                "title": "周日聚餐",
                "summary": "周日中午聚餐。",
                "status": "open",
                "source_seqs": [1],
                "cross_decision": "related",
            }
        ],
    )

    outage = Event.objects.get(space=space, event_key="order-db-outage")
    lunch = Event.objects.get(space=space, event_key="sunday-lunch")
    assert Event.objects.filter(space=space).count() == 2
    assert outage.status == Event.Status.DONE
    assert set(
        EventEvidence.objects.filter(event=outage).values_list(
            "message_id", flat=True
        )
    ) == {sales_message.pk, ops_message.pk}
    assert list(
        EventEvidence.objects.filter(event=lunch).values_list(
            "message_id", flat=True
        )
    ) == [weekend_message.pk]


def test_token_budget_splits_long_text_and_keeps_a_reply_with_its_parent(
    monkeypatch, settings
):
    settings.CHAT_ANALYSIS_LLM_ENABLED = True
    owner = User.objects.create_user(username="budget-owner")
    space = make_space(owner, "budget-space")
    conversation = _group(space, "budget-chat")
    body = "故障排查" * 80
    first = add_message(conversation, 1, text=body)
    second = add_message(conversation, 2, text=body)
    third = add_message(conversation, 3, text=body)
    job = make_job(space, owner, conversation, end_seq=3, key="budget-job")
    job.specification["scheduled_message_scope"] = True
    job.save(update_fields=("specification",))
    for message in (first, second, third):
        AnalysisJobMessage.objects.create(job=job, message=message)
    messages = [first, second, third]

    def width(budget):
        settings.CHAT_ANALYSIS_MODEL_INPUT_TOKENS = budget
        try:
            return len(execution._messages_for_model(job, messages))
        except MessageExceedsBudget:
            return 0

    low, high = 1, 20000
    while width(high) < 2:
        high *= 2
    while low + 1 < high:
        mid = (low + high) // 2
        if width(mid) >= 2:
            high = mid
        else:
            low = mid
    assert width(high) == 2
    third.reply_to = second
    third.save(update_fields=("reply_to",))
    settings.CHAT_ANALYSIS_MODEL_INPUT_TOKENS = high
    assert [
        item.pk for item in execution._messages_for_model(job, messages)
    ] == [first.pk]

    seen = []
    monkeypatch.setattr(
        "chat_analysis.execution._prepare_chunk", lambda *_args: (None, None)
    )
    monkeypatch.setattr(
        "chat_analysis.execution._write_chunk_note",
        lambda _job, chunk, *_results: seen.append([item.pk for item in chunk])
        or (True, False),
    )
    result = execution.execute_analysis_job(job.pk, worker_id="budget")
    assert seen == [[first.pk], [second.pk, third.pk]]
    assert result.job.state == AnalysisJob.State.READY
    assert AnalysisJobMessage.objects.filter(
        job=job, completed_at__isnull=False
    ).count() == 3


def test_queued_and_running_are_distinct_sync_states():
    owner = User.objects.create_user(username="sync-state-owner")
    space = make_space(owner, "sync-state-space")
    conversation = _group(space, "sync-state")
    stored = timezone.now()
    queued_message = _store(
        add_message(conversation, 1, text="排队"),
        owner,
        space,
        "sync-queued",
        stored,
    )
    running_message = _store(
        add_message(conversation, 2, text="分析中"),
        owner,
        space,
        "sync-running",
        stored,
    )
    waiting_batch = UploadBatch.objects.get(
        items__chat_message_origins__message=queued_message
    )
    running_batch = UploadBatch.objects.get(
        items__chat_message_origins__message=running_message
    )
    plain = UploadBatch.objects.create(
        space=space,
        uploaded_by=owner,
        source_type="wechat",
        idempotency_key="sync-plain",
        status=UploadBatch.Status.COMPLETED,
        completed_at=stored,
    )
    queued = make_job(
        space, owner, conversation, end_seq=1, key="sync-queued-job"
    )
    running = make_job(
        space, owner, conversation, end_seq=2, key="sync-running-job"
    )
    queued.state = AnalysisJob.State.QUEUED
    running.state = AnalysisJob.State.RUNNING
    queued.save(update_fields=("state",))
    running.save(update_fields=("state",))
    queued.upload_batches.add(waiting_batch)
    running.upload_batches.add(running_batch)

    summaries = _analysis_summaries([waiting_batch, running_batch, plain])
    assert summaries[waiting_batch.pk]["state"] == "queued"
    assert summaries[waiting_batch.pk]["queued"] is True
    assert summaries[waiting_batch.pk]["running"] is False
    assert summaries[waiting_batch.pk]["duration_seconds"] is None
    assert summaries[running_batch.pk]["state"] == "running"
    assert summaries[running_batch.pk]["running"] is True
    assert summaries[plain.pk]["state"] == ""
    assert summaries[plain.pk]["job_count"] == 0


def test_analysis_tasks_use_the_dedicated_queue(monkeypatch):
    monkeypatch.setenv("CHAT_UPLOAD_DEDICATED_QUEUE", "true")
    routes = run_path(celery_settings.__file__)["CELERY_TASK_ROUTES"]
    assert (
        routes["chat_analysis.tasks.execute_analysis_job_task"]["queue"]
        == "chat_analysis"
    )
    assert (
        routes["chat_ingestion.tasks.parse_chat_upload_task"]["queue"]
        == "chat_ingestion"
    )

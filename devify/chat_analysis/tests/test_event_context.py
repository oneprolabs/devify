"""Regression tests for using prior chat as context, not new activity."""

from datetime import timedelta

import pytest
from django.contrib.auth.models import User
from django.utils import timezone

from chat_analysis import execution
from chat_analysis.models import AnalysisJob, AnalysisJobMessage, Event, EventEvidence

from chat_domain.models import Message, MessagePart

from .test_event_extraction import (
    add_message,
    make_conversation,
    make_job,
    make_space,
    run_job,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def chat(settings):
    settings.CHAT_ANALYSIS_LLM_ENABLED = True
    settings.CHAT_ANALYSIS_AUTO_CREATE_EVENTS = True
    settings.CHAT_ANALYSIS_MODEL_UUID = None
    owner = User.objects.create_user(username="event-context")
    space = make_space(owner, "event-context")
    return owner, space, make_conversation(space, "payments", "付款讨论")


@pytest.fixture(params=[False, True], ids=["immediate", "scheduled"])
def analyze_current(request, chat, monkeypatch):
    owner, space, conversation = chat

    def analyze(message, candidates):
        job = make_job(space, owner, conversation, end_seq=message.ingest_seq)
        job.start_seq = message.ingest_seq - 1
        if request.param:
            job.specification["scheduled_message_scope"] = True
            AnalysisJobMessage.objects.create(job=job, message=message)
        job.save(update_fields=("start_seq", "specification"))
        captured = run_job(job, monkeypatch, candidates, [])
        assert job.state == AnalysisJob.State.READY, job.error
        assert len(captured) == 1
        return captured[0]

    return analyze


def test_previous_text_and_quoted_parent_are_separate_from_current_messages(
    chat, analyze_current,
):
    _, space, conversation = chat
    parent = add_message(conversation, 1, "订单 A 验收通过后再安排付款。")
    recent = add_message(conversation, 2, "财务在等付款回执。")
    parallel = make_conversation(space, "other", "另外的付款讨论")
    add_message(parallel, 2, "另外一个群在确认不同订单。")
    current = add_message(
        conversation, 3, "请确认万事达卡转账。", reply_to=parent,
    )
    future = add_message(conversation, 4, "之后才确认已经到账。")

    _, payload = analyze_current(current, [])

    assert [item["seq"] for item in payload["messages"]] == [current.ingest_seq]
    assert payload["messages"][0]["reply_to_seq"] == parent.ingest_seq
    context = [(item["seq"], item["text"]) for item in payload["context_messages"]]
    assert sorted(context) == [
        (parent.ingest_seq, "订单 A 验收通过后再安排付款。"),
        (recent.ingest_seq, "财务在等付款回执。"),
    ]
    assert not any(seq == future.ingest_seq for seq, _ in context)
    assert not Event.objects.filter(space=space).exists()


def test_reply_to_another_conversation_does_not_expose_its_text(
    chat, analyze_current,
):
    _, space, conversation = chat
    other = make_conversation(space, "other", "另外的付款讨论")
    foreign = add_message(other, 1, "另外一个群的付款前置条件。")
    current = add_message(
        conversation, 2, "请确认万事达卡转账。", reply_to=foreign,
    )

    _, payload = analyze_current(current, [])

    assert payload["context_messages"] == []


def proposed_payment(*sources):
    return {
        "action": "create",
        "title": "订单 A 付款",
        "summary": "订单 A 验收后付款，目前待确认转账。",
        "status": "open",
        "sources": [{"seq": seq, "role": role} for seq, role in sources],
    }


def test_context_and_current_can_both_be_published_as_evidence(chat, analyze_current):
    _, space, conversation = chat
    context = add_message(conversation, 1, "订单 A 验收后付款。")
    current = add_message(conversation, 2, "请确认万事达卡转账。")

    analyze_current(current, [proposed_payment((1, "background"), (2, "matter"))])

    event = Event.objects.get(space=space)
    assert event.title == "订单 A 付款"
    assert "验收后付款" in event.content
    assert set(event.evidence.values_list("message_id", flat=True)) == {
        context.pk, current.pk,
    }


@pytest.mark.parametrize(
    "sources",
    [
        [(1, "background")],
        [(1, "matter")],
        [(1, "background"), (2, "background")],
        [(1, "background"), (3, "matter")],
    ],
    ids=[
        "background-only", "context-disguised-as-current",
        "current-as-background", "future-disguised-as-current",
    ],
)
def test_no_event_without_a_valid_current_citation(chat, analyze_current, sources):
    _, space, conversation = chat
    add_message(conversation, 1, "订单 A 验收后付款。")
    current = add_message(conversation, 2, "请确认万事达卡转账。")
    add_message(conversation, 3, "之后才确认已经到账。")

    analyze_current(current, [proposed_payment(*sources)])

    assert not Event.objects.filter(space=space).exists()


def test_unclear_decision_does_not_publish_even_with_current_citation(
    chat, analyze_current,
):
    _, space, conversation = chat
    current = add_message(conversation, 1, "请确认万事达卡转账。")
    possible_event = proposed_payment((1, "matter"))
    possible_event["context_decision"] = "unclear"

    analyze_current(current, [possible_event])

    assert not Event.objects.filter(space=space).exists()


def test_newer_background_does_not_apply_status_from_late_upload(
    chat, analyze_current,
):
    owner, space, conversation = chat
    now = timezone.now()
    current_latest = add_message(conversation, 1, "付款仍未到账，继续核对。")
    background = add_message(conversation, 2, "财务说明查账流程。")
    late = add_message(conversation, 3, "已经到账。", reply_to=background)
    late.occurred_at = now - timedelta(days=1)
    late.save(update_fields=("occurred_at",))
    event = Event.objects.create(
        space=space, created_by=owner, event_key="payment-check",
        title="订单 A 付款", content="付款仍未到账，继续核对。",
        status=Event.Status.IN_PROGRESS,
        last_activity_at=current_latest.occurred_at,
    )
    EventEvidence.objects.create(
        event=event, message=current_latest, created_by=owner,
    )
    candidate = {
        **proposed_payment((2, "background"), (3, "matter")),
        "action": "attach",
        "event_key": event.event_key,
        "status": "done",
        "status_scope": "event",
    }

    analyze_current(late, [candidate])

    event.refresh_from_db()
    assert event.status == Event.Status.IN_PROGRESS
    assert event.content == "付款仍未到账，继续核对。"
    assert set(event.evidence.values_list("message_id", flat=True)) == {
        current_latest.pk, background.pk, late.pk,
    }



@pytest.mark.parametrize("scenario", ["standalone", "dependent", "conditional", "unclear"])
def test_same_request_has_different_outcome_based_on_context(
    chat, analyze_current, scenario,
):
    owner, space, conversation = chat
    context_by_scenario = {
        "standalone": "独立结算这笔差旅报销，不关联其他订单，核对卡转账回执。",
        "dependent": "订单 A 付款已经发起，下一步核对卡转账回执。",
        "conditional": "订单 A 仅在验收通过后才能付款。目前尚未验收。",
    }
    antecedent = context_by_scenario.get(scenario)
    parent = add_message(conversation, 1, antecedent) if antecedent else None
    current = add_message(conversation, 2, "请确认万事达卡转账。", reply_to=parent)
    event = None
    if scenario == "dependent":
        event = Event.objects.create(
            space=space, created_by=owner, event_key="order-a-payment",
            title="订单 A 付款", content=antecedent, status=Event.Status.IN_PROGRESS,
            last_activity_at=parent.occurred_at,
        )
        EventEvidence.objects.create(event=event, message=parent, created_by=owner)

    result = proposed_payment(*([(1, "background")] if parent else []), (2, "matter"))
    result["context_decision"] = "independent"
    if scenario == "standalone":
        result.update(title="差旅报销结算", summary="独立差旅报销，待核对转账回执。")
    elif scenario == "dependent":
        result.update(
            action="attach", context_decision="continuation", event_key=event.event_key,
            summary="订单 A 付款已发起，仍待核对卡转账回执。",
        )
    elif scenario == "conditional":
        result["summary"] = "订单 A 尚未验收；验收通过后才可付款和核对转账。"
    else:
        result["context_decision"] = "unclear"

    _, payload = analyze_current(current, [result])
    assert [item["text"] for item in payload["context_messages"]] == (
        [antecedent] if antecedent else []
    )
    if scenario == "unclear":
        assert not Event.objects.filter(space=space).exists()
        return
    actual = Event.objects.get(space=space)
    assert actual.title == result["title"]
    assert actual.content == result["summary"]
    assert actual.status != Event.Status.DONE
    assert actual.evidence.filter(message=current).exists()
    if event is not None:
        assert actual.pk == event.pk
        assert actual.status == Event.Status.IN_PROGRESS


def test_scheduled_media_only_chunk_does_not_block_next_text(chat, monkeypatch):
    owner, space, conversation = chat
    image = Message.objects.create(
        conversation=conversation, message_key="image-1", ingest_seq=1,
        occurred_at=timezone.now(),
    )
    MessagePart.objects.create(message=image, part_key="img", kind=MessagePart.Kind.IMAGE)
    text = add_message(conversation, 2, "确认安排下周的验收会议。")
    job = make_job(space, owner, conversation, end_seq=2)
    job.specification["scheduled_message_scope"] = True
    job.save(update_fields=("specification",))
    for message in (image, text):
        AnalysisJobMessage.objects.create(job=job, message=message)
    monkeypatch.setattr(execution, "ANALYSIS_CHUNK_SIZE", 1)
    captured = run_job(job, monkeypatch, [
        {**proposed_payment((2, "matter")), "title": "安排验收会议"},
    ], [])
    assert len(captured) == 1
    assert job.state == AnalysisJob.State.READY
    assert job.scheduled_messages.filter(completed_at__isnull=False).count() == 2
    assert Event.objects.get(space=space).evidence.filter(message=text).exists()



def test_new_correction_updates_summary_and_keeps_original_evidence(chat, analyze_current):
    owner, space, conversation = chat
    original = add_message(conversation, 1, "订单 A 已到账。")
    corrected = add_message(
        conversation, 2, "刚才说错了，只提交了转账申请，款项未到账。",
        reply_to=original,
    )
    event = Event.objects.create(
        space=space, created_by=owner, event_key="order-a-payment",
        title="订单 A 付款", content="订单 A 已到账。", status=Event.Status.DONE,
        last_activity_at=original.occurred_at,
    )
    EventEvidence.objects.create(event=event, message=original, created_by=owner)
    new_summary = "订单 A 只提交了转账申请，尚未到账，继续核对。"
    _, payload = analyze_current(corrected, [{
        **proposed_payment((1, "background"), (2, "matter")),
        "action": "attach", "event_key": event.event_key,
        "context_decision": "continuation", "status_scope": "event",
        "status": "in_progress", "summary": new_summary,
    }])
    assert payload["context_messages"][0]["text"] == "订单 A 已到账。"
    event.refresh_from_db()
    assert event.content == new_summary
    assert event.status == Event.Status.IN_PROGRESS
    assert set(event.evidence.values_list("message_id", flat=True)) == {
        original.pk, corrected.pk,
    }

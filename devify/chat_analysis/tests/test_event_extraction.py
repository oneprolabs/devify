import json

import pytest
from django.contrib.auth.models import User
from django.utils import timezone

from chat_analysis import execution
from chat_analysis.models import (
    Event,
    EventEvidence,
    EventSuggestion,
)
from chat_analysis.services import (
    create_analysis_job,
    create_note,
    refresh_event_window,
)
from chat_domain.models import Conversation, Message, MessagePart
from spaces.models import Space, SpaceMembership

pytestmark = [pytest.mark.django_db]


def make_space(owner, slug="event-extract"):
    space = Space.objects.create(
        name=slug, slug=slug, kind=Space.Kind.TEAM, owner=owner
    )
    SpaceMembership.objects.create(
        space=space, user=owner, role=SpaceMembership.Role.OWNER
    )
    return space


def make_conversation(space, key, title):
    return Conversation.objects.create(
        space=space,
        platform=Conversation.Platform.WECHAT,
        source_namespace="local",
        source_conversation_id=key,
        identity_key=f"wechat:local:{key}-{space.pk}",
        title=title,
        kind=Conversation.Kind.GROUP,
    )


def add_message(
    conversation, index, text, sender="Alice", reply_to=None
):
    message = Message.objects.create(
        conversation=conversation,
        message_key=f"m-{index}",
        ingest_seq=index,
        occurred_at=timezone.now(),
        sender_name=sender,
        reply_to=reply_to,
    )
    MessagePart.objects.create(
        message=message,
        part_key="text-0",
        kind=MessagePart.Kind.TEXT,
        ordinal=0,
        text=text,
    )
    return message


def make_job(space, owner, conversation, end_seq, key="job"):
    return create_analysis_job(
        actor=owner,
        space=space,
        conversation=conversation,
        request_key=key,
        end_seq=end_seq,
        input_version="v1",
    )


def fake_llm(events, captured):
    def side_effect(*, prompt, content, json_mode, node_name, state):
        if node_name == "chat_event_extraction":
            captured.append((prompt, json.loads(content)))
            return {"events": events}, {"model": "test"}
        return (
            {"facts": [], "actions": [], "risks": [], "decisions": []},
            {"model": "test"},
        )

    return side_effect


def run_job(job, monkeypatch, events, captured):
    monkeypatch.setattr(
        execution.LLMTracker,
        "call_and_track",
        fake_llm(events, captured),
    )
    execution.execute_analysis_job(job.pk, worker_id="extract-test")
    job.refresh_from_db()
    return captured


@pytest.mark.django_db
def test_payload_includes_reply_and_conversation(settings, monkeypatch):
    settings.CHAT_ANALYSIS_LLM_ENABLED = True
    owner = User.objects.create_user(username="extract-payload")
    space = make_space(owner, "payload-space")
    conversation = make_conversation(space, "sales", "销售群")
    first = add_message(conversation, 1, "明天给报价")
    add_message(conversation, 2, "收到", reply_to=first)
    job = make_job(space, owner, conversation, end_seq=2)
    captured = run_job(job, monkeypatch, [], [])
    prompt, payload = captured[0]
    assert payload["conversation_title"] == "销售群"
    assert payload["messages"][1]["reply_to_seq"] == 1
    assert payload["messages"][1]["text"] == "收到"
    assert "trackable matter" in prompt
    assert "Event granularity:" in prompt


@pytest.mark.django_db
def test_confirmation_attaches_and_does_not_mark_done(
    settings, monkeypatch
):
    settings.CHAT_ANALYSIS_LLM_ENABLED = True
    settings.CHAT_ANALYSIS_AUTO_CREATE_EVENTS = True
    owner = User.objects.create_user(username="extract-confirm")
    space = make_space(owner, "confirm-space")
    conversation = make_conversation(space, "ops", "运维群")
    first = add_message(conversation, 1, "明天给报价", sender="Bob")
    add_message(conversation, 2, "收到", sender="Alice", reply_to=first)
    event = Event.objects.create(
        space=space,
        created_by=owner,
        event_key="quote-follow-up",
        title="明天给报价",
        content="等待报价。",
        status=Event.Status.OPEN,
    )
    EventEvidence.objects.create(
        event=event, message=first, created_by=owner
    )
    refresh_event_window(event, messages=[first])
    job = make_job(space, owner, conversation, end_seq=2)
    captured = run_job(
        job,
        monkeypatch,
        [
            {
                "action": "attach",
                "event_key": "quote-follow-up",
                "title": "明天给报价",
                "summary": "Alice 已确认，仍待报价。",
                "status": "done",
                "sources": [
                    {
                        "seq": 2,
                        "conversation_title": "运维群",
                        "role": "confirmation",
                    }
                ],
            }
        ],
        [],
    )
    same = captured[0][1]["open_events_same_conversation"]
    assert same[0]["event_key"] == "quote-follow-up"
    event.refresh_from_db()
    assert Event.objects.filter(space=space).count() == 1
    assert EventEvidence.objects.filter(event=event).count() == 2
    assert event.status == Event.Status.IN_PROGRESS
    assert event.content == "等待报价。"


@pytest.mark.django_db
def test_cross_candidates_only_include_overlapping_matters(
    settings, monkeypatch
):
    settings.CHAT_ANALYSIS_LLM_ENABLED = True
    settings.CHAT_ANALYSIS_AUTO_CREATE_EVENTS = True
    owner = User.objects.create_user(username="extract-cross")
    space = make_space(owner, "cross-space")
    sales = make_conversation(space, "sales", "销售群")
    weekend = make_conversation(space, "weekend", "周末群")
    current = make_conversation(space, "quote", "报价群")
    sales_msg = add_message(sales, 1, "客户A报价", sender="Bob")
    weekend_msg = add_message(weekend, 1, "周六吃饭", sender="Carol")
    add_message(current, 1, "客户A报价跟进", sender="Alice")
    quote = Event.objects.create(
        space=space,
        created_by=owner,
        event_key="customer-a-quote",
        title="客户A报价",
        content="跟进报价。",
        status=Event.Status.OPEN,
        entity_key="customer-a",
    )
    outing = Event.objects.create(
        space=space,
        created_by=owner,
        event_key="weekend-dinner",
        title="周六吃饭",
        content="聚餐。",
        status=Event.Status.OPEN,
    )
    EventEvidence.objects.create(
        event=quote, message=sales_msg, created_by=owner
    )
    EventEvidence.objects.create(
        event=outing, message=weekend_msg, created_by=owner
    )
    job = make_job(space, owner, current, end_seq=1, key="cross-job")
    captured = run_job(
        job,
        monkeypatch,
        [
            {
                "action": "create",
                "title": "客户A报价跟进",
                "summary": "继续跟进客户A报价。",
                "status": "open",
                "source_seqs": [1],
                "cross_decision": "related",
            }
        ],
        [],
    )
    payload = captured[0][1]
    keys = [item["event_key"] for item in payload["cross_candidates"]]
    assert "customer-a-quote" in keys
    assert "weekend-dinner" not in keys
    assert payload["open_events_same_conversation"] == []


@pytest.mark.django_db
def test_drop_rejects_pending_suggestion_not_accepted_event(
    settings, monkeypatch
):
    settings.CHAT_ANALYSIS_LLM_ENABLED = True
    settings.CHAT_ANALYSIS_AUTO_CREATE_EVENTS = True
    owner = User.objects.create_user(username="extract-drop")
    space = make_space(owner, "drop-space")
    conversation = make_conversation(space, "chat", "闲聊群")
    message = add_message(conversation, 1, "哈哈")
    kept = Event.objects.create(
        space=space,
        created_by=owner,
        event_key="real-follow-up",
        title="真实跟进",
        content="需要回复。",
        status=Event.Status.OPEN,
    )
    EventEvidence.objects.create(
        event=kept, message=message, created_by=owner
    )
    job = make_job(space, owner, conversation, end_seq=1)
    note = create_note(
        actor=owner,
        space=space,
        note_key="seed-note",
        title="seed",
        content="seed",
        analysis_job=job,
    )
    pending = EventSuggestion.objects.create(
        space=space,
        analysis_job=job,
        note=note,
        created_by=owner,
        event_key="small-talk",
        title="哈哈",
        summary="闲聊。",
    )
    run_job(
        job,
        monkeypatch,
        [
            {
                "action": "drop",
                "event_key": "small-talk",
                "title": "哈哈",
                "summary": "闲聊。",
            },
            {
                "action": "drop",
                "event_key": "real-follow-up",
                "title": "真实跟进",
                "summary": "需要回复。",
            },
        ],
        [],
    )
    pending.refresh_from_db()
    kept.refresh_from_db()
    assert pending.status == EventSuggestion.Status.REJECTED
    assert Event.objects.filter(pk=kept.pk).exists()
    assert kept.status == Event.Status.OPEN

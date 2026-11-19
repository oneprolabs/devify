"""Regression cases for evidence-backed follow-ups to existing events."""

import json

import pytest
from django.contrib.auth.models import User

from chat_analysis import execution
from chat_analysis.models import (
    AnalysisJob,
    AnalysisJobMessage,
    Event,
    EventEvidence,
    EventSuggestion,
)
from chat_analysis.services import refresh_event_window

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
    owner = User.objects.create_user(username="event-followup")
    space = make_space(owner, "event-followup")
    return owner, space, make_conversation(space, "client", "客户端群")


@pytest.fixture(params=[False, True], ids=["immediate", "scheduled"])
def run_followup(request, chat, monkeypatch):
    owner, space, conversation = chat

    def run(message, candidates):
        job = make_job(space, owner, conversation, end_seq=message.ingest_seq)
        job.start_seq = message.ingest_seq - 1
        if request.param:
            job.specification = {
                **job.specification, "scheduled_message_scope": True,
            }
            AnalysisJobMessage.objects.create(job=job, message=message)
        job.save(update_fields=("start_seq", "specification"))
        captured = run_job(job, monkeypatch, candidates, [])
        assert job.state == AnalysisJob.State.READY, job.error
        assert len(captured) == 1
        return captured[0][1]

    return run


def existing_event(chat, *, key, title, status, source_text, entity=""):
    owner, space, conversation = chat
    source = add_message(conversation, 1, source_text)
    event = Event.objects.create(
        space=space,
        created_by=owner,
        event_key=key,
        title=title,
        content=source_text,
        entity_key=entity,
        status=status,
    )
    EventEvidence.objects.create(event=event, message=source, created_by=owner)
    refresh_event_window(event, messages=[source])
    return event


def candidate(action, *, key="", status="in_progress", seq=None, scope=None):
    result = {
        "action": action,
        "event_key": key,
        "title": "客户端发版验证",
        "summary": "客户端验证结果有更新。",
        "status": status,
    }
    if seq is not None:
        result["sources"] = [{"seq": seq, "role": "matter"}]
    if scope is not None:
        result["status_scope"] = scope
    return result


@pytest.mark.parametrize("target_exists", [False, True], ids=["missing", "hidden"])
def test_unshown_attach_is_ignored_not_created(chat, run_followup, target_exists):
    _, space, conversation = chat
    target = "other-client-release"
    if target_exists:
        existing_event(
            chat, key=target, title="另一轮客户端发版", status=Event.Status.DONE,
            source_text="上一轮客户端已完成验收。",
        )
    message = add_message(conversation, 2, "这次复测仍能复现。")
    payload = run_followup(message, [candidate("attach", key=target, seq=2)])

    assert target not in {
        item["event_key"]
        for pool in ("open_events_same_conversation", "cross_candidates")
        for item in payload[pool]
    }
    keys = Event.objects.filter(space=space).values_list("event_key", flat=True)
    assert list(keys) == ([target] if target_exists else [])
    assert not EventEvidence.objects.filter(message=message).exists()
    assert not EventSuggestion.objects.filter(space=space).exists()


@pytest.mark.parametrize("action", ["create", "attach"])
@pytest.mark.parametrize("bad_seq", [None, 1], ids=["missing", "outside-chunk"])
def test_explicit_auto_write_requires_current_citation(
    chat, run_followup, action, bad_seq,
):
    _, space, conversation = chat
    event = existing_event(
        chat, key="client-release", title="客户端发版",
        status=Event.Status.IN_PROGRESS, source_text="开始发版验证。",
    )
    message = add_message(conversation, 2, "登录已复测。")
    payload = run_followup(message, [candidate(
        action, key=event.event_key if action == "attach" else "", seq=bad_seq,
    )])

    assert event.event_key in {
        item["event_key"] for item in payload["open_events_same_conversation"]
    }
    assert Event.objects.filter(space=space).count() == 1
    assert not EventEvidence.objects.filter(message=message).exists()
    assert not EventSuggestion.objects.filter(space=space).exists()


def test_create_with_current_citation_is_published(chat, run_followup):
    _, space, conversation = chat
    message = add_message(conversation, 1, "请验证下一版客户端登录。")
    run_followup(message, [candidate("create", seq=1)])

    event = Event.objects.get(space=space)
    assert event.evidence.filter(message=message).exists()


@pytest.mark.parametrize("scope", [None, "progress", "event"])
@pytest.mark.parametrize(
    ("before", "proposed", "text"),
    [
        (Event.Status.IN_PROGRESS, Event.Status.DONE, "客户端发版已验收。"),
        (Event.Status.DONE, Event.Status.IN_PROGRESS, "同一问题又复现，需要重开。"),
    ],
    ids=["close", "reopen"],
)
def test_attach_changes_event_state_only_with_event_scope(
    chat, run_followup, scope, before, proposed, text,
):
    _, space, conversation = chat
    event = existing_event(
        chat, key="client-release", title="客户端发版", status=before,
        source_text="跟进客户端发版。",
    )
    original = event.evidence.get().message
    message = add_message(conversation, 2, text, reply_to=original)
    run_followup(message, [candidate(
        "attach", key=event.event_key, status=proposed, seq=2, scope=scope,
    )])

    event.refresh_from_db()
    assert Event.objects.filter(space=space).count() == 1
    assert event.evidence.filter(message=message).exists()
    assert event.status == (proposed if scope == "event" else before)


@pytest.mark.parametrize(
    ("label", "entity", "followup", "anchored"),
    [
        ("INC-12345", "inc12345", "继续跟进 INC-12345 的复测。", True),
        ("客户端发布 0.1.11", "", "客户端发布 0.1.11 还需一次复验。", True),
        ("客户端发布 0.1.11", "", "0.1.11 还需一次复验。", False),
    ],
    ids=["ticket", "qualified-release", "bare-version"],
)
def test_closed_event_candidate_requires_concrete_anchor(
    chat, run_followup, label, entity, followup, anchored,
):
    owner, space, conversation = chat
    old = existing_event(
        chat, key="previous-client-work", title=f"{label}：安装验证",
        status=Event.Status.DONE, source_text=f"{label} 的安装已验收。",
        entity=entity,
    )
    newer = add_message(conversation, 2, "等另一轮报告。")
    unrelated = Event.objects.create(
        space=space, created_by=owner, event_key="unrelated-work",
        title="报告待提交", status=Event.Status.OPEN,
        last_activity_at=newer.occurred_at,
    )
    EventEvidence.objects.create(event=unrelated, message=newer, created_by=owner)
    message = add_message(conversation, 3, followup)
    payload = run_followup(message, [])

    keys = [item["event_key"] for item in payload["open_events_same_conversation"]]
    assert unrelated.event_key in keys
    if anchored:
        assert keys[0] == old.event_key
    else:
        assert old.event_key not in keys



def test_release_progress_groups_without_closing_or_absorbing_other_work(
    chat, monkeypatch,
):
    owner, space, conversation = chat
    rows = [
        ("客户端发布 0.1.11", "这轮客户端发布 0.1.11 要修登录并复测。"),
        ("登录复测", "这轮发版的登录复测通过，并发检查还没做。"),
        ("WhatsApp 接入", "WhatsApp 接入单独交付和验收。"),
        ("转账", "请另外确认万事达卡转账。"),
    ]
    job = make_job(space, owner, conversation, end_seq=len(rows))
    job.specification["scheduled_message_scope"] = True
    job.save(update_fields=("specification",))
    for seq, (_, text) in enumerate(rows, 1):
        message = add_message(conversation, seq, text)
        AnalysisJobMessage.objects.create(job=job, message=message)

    def model(*, prompt, content, json_mode, node_name, state):
        if node_name == "chat_event_extraction":
            return {"events": [
                {
                    **candidate(
                        "create", seq=seq, scope="event",
                        status="done" if seq == 2 else "open",
                    ),
                    "title": title,
                    "summary": text,
                }
                for seq, (title, text) in enumerate(rows, 1)
            ]}, {}
        if node_name == "chat_event_reduce":
            items = json.loads(content)["candidates"]
            assert [item["title"] for item in items] == [r[0] for r in rows]
            return {"groups": [[0, 1]]}, {}
        return {}, {}

    monkeypatch.setattr(execution.LLMTracker, "call_and_track", model)
    execution.execute_analysis_job(job.pk, worker_id="release-test")

    events = {event.title: event for event in Event.objects.filter(space=space)}
    assert set(events) == {rows[0][0], rows[2][0], rows[3][0]}
    release = events[rows[0][0]]
    assert release.status == Event.Status.OPEN
    assert set(release.evidence.values_list("message__ingest_seq", flat=True)) == {
        1, 2,
    }

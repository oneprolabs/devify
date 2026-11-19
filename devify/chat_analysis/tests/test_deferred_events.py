"""Exercise deferred event candidates through the real analysis and publish paths."""

import pytest
from django.contrib.auth.models import User
from django.utils import timezone

from chat_analysis import execution
from chat_analysis.models import (
    AnalysisJob,
    AnalysisJobMessage,
    DeferredEventCandidate,
    Event,
    EventEvidence,
    EventSuggestion,
)

from .test_event_extraction import (
    add_message,
    make_conversation,
    make_job,
    make_space,
    run_job,
)

pytestmark = pytest.mark.django_db

ANCHOR_TEXT = "这两笔付款里，这笔今天一定要确认。"
QUESTION = "今天要确认的是订单 A 还是订单 B？"


@pytest.fixture
def chat(settings):
    settings.CHAT_ANALYSIS_LLM_ENABLED = True
    settings.CHAT_ANALYSIS_AUTO_CREATE_EVENTS = True
    settings.CHAT_ANALYSIS_MODEL_UUID = None
    owner = User.objects.create_user(username="deferred-events")
    space = make_space(owner, "deferred-events")
    return owner, space, make_conversation(space, "payments", "付款讨论")


@pytest.fixture(params=[False, True], ids=["immediate", "scheduled"])
def analyze(request, monkeypatch):
    def run(chat, message, output, *, key=None, before_publish=None):
        owner, space, conversation = chat
        job = make_job(
            space, owner, conversation, end_seq=message.ingest_seq,
            key=key or f"message-{message.pk}",
        )
        job.start_seq = message.ingest_seq - 1
        if request.param:
            job.specification.update(
                scheduled_message_scope=True,
                boundary=timezone.now().isoformat(),
            )
            AnalysisJobMessage.objects.create(job=job, message=message)
        job.save(update_fields=("start_seq", "specification"))
        captured = run_job(job, monkeypatch, output, [])
        assert job.state == AnalysisJob.State.READY, job.error
        assert len(captured) == 1
        if request.param:
            if before_publish:
                before_publish()
            execution.publish_ready_event_batches()
        return captured[0][1]

    return run


def defer(seq, *, signal="deadline", reason="ambiguous_target"):
    return {
        "action": "defer",
        "defer_reason": reason,
        "followup_question": QUESTION,
        "followup_signal": signal,
        "sources": [{"seq": seq, "role": "matter"}],
    }


def clarify(current, anchor, ids, *, action="create", key="", role="matter"):
    return {
        "action": action,
        "event_key": key,
        "context_decision": "continuation" if action == "attach" else "independent",
        "title": "核对订单 A 到账",
        "summary": "今天需确认订单 A 是否到账。",
        "status": "open",
        "sources": [
            {"seq": current.ingest_seq, "role": role},
            {"seq": anchor.ingest_seq, "role": "background"},
        ],
        "resolves_deferred_ids": ids,
    }


@pytest.mark.parametrize("bad_sources", [True, 1.2, {}, {"seq": 1}])
def test_malformed_citation_cannot_create_event(chat, analyze, bad_sources):
    _, space, conversation = chat
    message = add_message(conversation, 1, "请核对订单 A。")
    sources = [{"seq": bad_sources, "role": "matter"}] if not isinstance(bad_sources, dict) else bad_sources
    analyze(chat, message, [{
        "action": "create", "title": "核对订单 A", "summary": "请核对订单 A。",
        "status": "open", "sources": sources, "source_seqs": [1],
    }])
    assert not Event.objects.filter(space=space).exists()


@pytest.mark.parametrize("status", ["in_progress", "done"])
def test_bare_ack_never_advances_status_even_when_model_calls_it_matter(chat, analyze, status):
    owner, space, conversation = chat
    original = add_message(conversation, 1, "请核对订单 A。")
    event = Event.objects.create(
        space=space, created_by=owner, event_key="ack-ticket", title="核对订单 A",
        content="待核对。", status=Event.Status.OPEN,
    )
    EventEvidence.objects.create(event=event, message=original, created_by=owner)
    current = add_message(conversation, 2, "收到。", reply_to=original)
    analyze(chat, current, [{
        "action": "attach", "event_key": event.event_key, "title": event.title,
        "summary": "已收到。", "status": status, "status_scope": "event",
        "execution_seqs": [2], "sources": [{"seq": 2, "role": "matter"}],
    }])
    event.refresh_from_db()
    assert event.status == Event.Status.OPEN
    assert event.evidence.filter(message=current).exists()


@pytest.mark.parametrize("before", [Event.Status.OPEN, Event.Status.DONE])
def test_partial_execution_only_starts_open_event(chat, analyze, before):
    owner, space, conversation = chat
    original = add_message(conversation, 1, "请核对订单 A。")
    event = Event.objects.create(
        space=space, created_by=owner, event_key="partial-ticket", title="核对订单 A",
        content="核对账目。", status=before,
    )
    EventEvidence.objects.create(event=event, message=original, created_by=owner)
    current = add_message(conversation, 2, "已经核对第一笔，第二笔待查。", reply_to=original)
    analyze(chat, current, [{
        "action": "attach", "event_key": event.event_key, "title": event.title,
        "summary": "已核对第一笔。", "status": "in_progress", "status_scope": "progress",
        "execution_seqs": [2], "sources": [{"seq": 2, "role": "matter"}],
    }])
    event.refresh_from_db()
    assert event.status == (Event.Status.IN_PROGRESS if before == Event.Status.OPEN else before)
    assert event.evidence.filter(message=current).exists()


def test_unresolved_target_cannot_publish_as_create(chat, analyze):
    _, space, conversation = chat
    message = add_message(conversation, 1, ANCHOR_TEXT)
    analyze(chat, message, [{
        **defer(1), "action": "create", "target_resolution": "unresolved",
        "title": "确认订单 A/B", "summary": ANCHOR_TEXT, "status": "open",
    }])
    assert DeferredEventCandidate.objects.filter(message=message).count() == 1
    assert not Event.objects.filter(space=space).exists()


@pytest.mark.parametrize("execution_seqs,expected", [
    (None, Event.Status.OPEN), ([], Event.Status.OPEN),
    ([99], Event.Status.OPEN), ([1], Event.Status.IN_PROGRESS),
])
def test_new_event_needs_current_execution_evidence(chat, analyze, execution_seqs, expected):
    _, space, conversation = chat
    message = add_message(
        conversation, 1,
        "我已开始对银行流水。" if execution_seqs == [1] else "请今天核对订单A。",
    )
    candidate = {
        "action": "create", "title": "核对订单A", "summary": "核对银行流水。",
        "status": "in_progress", "status_scope": "event",
        "sources": [{"seq": 1, "role": "matter"}],
    }
    if execution_seqs is not None:
        candidate["execution_seqs"] = execution_seqs
    analyze(chat, message, [candidate])
    assert Event.objects.get(space=space).status == expected


@pytest.mark.parametrize("direct_reply", [True, False])
def test_selected_candidate_can_recover_background_from_direct_reply(chat, analyze, direct_reply):
    _, space, conversation = chat
    anchor, candidate = defer_first(chat, analyze)
    current = add_message(
        conversation, 2, "我说的是订单 A，今天核对到账。",
        reply_to=anchor if direct_reply else None,
    )
    output = clarify(current, anchor, [candidate.pk])
    output["event_change"] = "material"
    output["sources"] = output["sources"][:1]
    analyze(chat, current, [output])
    event = Event.objects.get(space=space)
    candidate.refresh_from_db()
    assert event.evidence.filter(message=anchor).exists() == direct_reply
    assert candidate.status == (
        DeferredEventCandidate.Status.RESOLVED if direct_reply
        else DeferredEventCandidate.Status.PENDING
    )


@pytest.mark.parametrize("basis,basis_seqs,status,published", [
    ("none", [1], "open", False), ("explicit_work", [99], "open", False),
    ("explicit_work", [1], "open", True), ("lasting_result", [1], "open", False),
    ("lasting_result", [1], "done", True),
])
def test_event_admission_needs_current_basis(chat, analyze, basis, basis_seqs, status, published):
    _, space, conversation = chat
    text = "财务已签批并归档预算单。" if status == "done" else "请财务明天核对到账。"
    message = add_message(conversation, 1, text)
    analyze(chat, message, [{
        "action": "create", "title": "核对事项", "summary": text,
        "status": status, "status_scope": "event", "new_event_basis": basis,
        "basis_seqs": basis_seqs, "sources": [{"seq": 1, "role": "matter"}],
    }])
    assert Event.objects.filter(space=space).exists() == published
    if published:
        assert Event.objects.get(space=space).status == status


def defer_first(chat, analyze):
    _, space, conversation = chat
    anchor = add_message(conversation, 1, ANCHOR_TEXT)
    analyze(chat, anchor, [defer(anchor.ingest_seq)])
    candidate = DeferredEventCandidate.objects.get(message=anchor)
    assert candidate.space_id == space.pk
    assert candidate.conversation_id == conversation.pk
    assert candidate.status == DeferredEventCandidate.Status.PENDING
    assert candidate.resolved_event_id is None
    return anchor, candidate


@pytest.mark.parametrize("same_candidate", [True, False])
def test_repeated_defer_requires_a_shown_candidate_and_original_evidence(
    chat, analyze, same_candidate,
):
    _, space, conversation = chat
    anchor, candidate = defer_first(chat, analyze)
    current = add_message(conversation, 2, "仍需今天核对，编号还没确认。", reply_to=anchor)
    output = defer(current.ingest_seq)
    output["same_deferred_id"] = candidate.pk if same_candidate else candidate.pk + 100
    output["sources"].append({"seq": anchor.ingest_seq, "role": "background"})

    analyze(chat, current, [output])

    candidate.refresh_from_db()
    assert candidate.status == DeferredEventCandidate.Status.PENDING
    assert DeferredEventCandidate.objects.filter(space=space).count() == (1 if same_candidate else 2)


def test_started_event_does_not_return_to_open_while_waiting(chat, analyze):
    owner, space, conversation = chat
    original = add_message(conversation, 1, "原件已交盖章窗口。")
    event = Event.objects.create(
        space=space, created_by=owner, event_key="fd552", title="原件盖章",
        content="正在办理。", status=Event.Status.IN_PROGRESS,
    )
    EventEvidence.objects.create(event=event, message=original, created_by=owner)
    current = add_message(conversation, 2, "窗口尚未盖章，改到明天办理。")
    analyze(chat, current, [{
        "action": "attach", "event_key": event.event_key,
        "context_decision": "continuation", "event_change": "material",
        "title": event.title, "summary": "原件已交窗口，明天继续办理。",
        "status": "open", "status_scope": "event",
        "sources": [{"seq": 2, "role": "matter"}],
    }])
    event.refresh_from_db()
    assert event.status == Event.Status.IN_PROGRESS
    assert event.evidence.filter(message=current).exists()


def test_unchanged_event_does_not_gain_evidence_when_another_event_changes(chat, analyze):
    owner, space, conversation = chat
    original = add_message(conversation, 1, "工单 A 与 B 都已经关闭。")
    for key in ("ticket-a", "ticket-b"):
        event = Event.objects.create(
            space=space, created_by=owner, event_key=key, title=key,
            content="已关闭。", status=Event.Status.DONE,
        )
        EventEvidence.objects.create(event=event, message=original, created_by=owner)
    current = add_message(
        conversation, 2, "A 已复现，我开始排查；B 不受影响，保持关闭。", reply_to=original,
    )
    output = {
        "action": "attach", "context_decision": "continuation", "title": "工单复核",
        "summary": "工单 A 已复现并开始排查。", "status": "in_progress",
        "status_scope": "event", "execution_seqs": [2],
        "sources": [{"seq": 2, "role": "matter"}],
    }
    analyze(chat, current, [
        {**output, "event_key": "ticket-a", "event_change": "material"},
        {**output, "event_key": "ticket-b", "event_change": "none"},
    ])

    changed = Event.objects.get(space=space, event_key="ticket-a")
    unchanged = Event.objects.get(space=space, event_key="ticket-b")
    assert changed.status == Event.Status.IN_PROGRESS
    assert changed.evidence.filter(message=current).exists()
    assert unchanged.status == Event.Status.DONE
    assert unchanged.content == "已关闭。"
    assert not unchanged.evidence.filter(message=current).exists()


@pytest.mark.parametrize(
    ("signal", "reason", "urgent"),
    [
        ("deadline", "ambiguous_target", True),
        ("payment", "conflicting_evidence", True),
        ("acceptance", "missing_context", True),
        ("blocked", "missing_context", True),
        ("action", "missing_context", False),
    ],
)
def test_deferring_keeps_evidence_out_of_formal_events(
    chat, analyze, signal, reason, urgent,
):
    _, space, conversation = chat
    anchor = add_message(conversation, 1, ANCHOR_TEXT)
    output = defer(anchor.ingest_seq, signal=signal, reason=reason)
    analyze(chat, anchor, [output, output])

    candidate = DeferredEventCandidate.objects.get(message=anchor)
    assert candidate.space_id == space.pk
    assert candidate.conversation_id == conversation.pk
    assert candidate.status == DeferredEventCandidate.Status.PENDING
    assert candidate.reason == reason
    assert candidate.question == QUESTION
    assert candidate.urgent is urgent
    assert candidate.resolution_suggestion_id is None
    assert candidate.resolved_event_id is None
    assert not Event.objects.filter(space=space).exists()
    assert not EventSuggestion.objects.filter(space=space).exists()


@pytest.mark.parametrize(
    "invalid", ["acknowledgment", "no_current_source", "invalid_signal"],
)
def test_only_actionable_current_evidence_can_be_deferred(chat, analyze, invalid):
    _, space, conversation = chat
    anchor = add_message(conversation, 1, ANCHOR_TEXT)
    text = "好的。" if invalid == "acknowledgment" else "今天必须确认。"
    current = add_message(conversation, 2, text, reply_to=anchor)
    output = defer(current.ingest_seq)
    if invalid == "no_current_source":
        output["sources"] = [{"seq": anchor.ingest_seq, "role": "background"}]
    elif invalid == "invalid_signal":
        output["followup_signal"] = "unclear"

    analyze(chat, current, [output])
    assert not DeferredEventCandidate.objects.filter(space=space).exists()
    assert not Event.objects.filter(space=space).exists()


@pytest.mark.parametrize("action", ["create", "attach"])
def test_clarification_resolves_once_and_preserves_both_sources(
    chat, analyze, action,
):
    owner, space, conversation = chat
    anchor, candidate = defer_first(chat, analyze)
    existing = None
    if action == "attach":
        existing = Event.objects.create(
            space=space, created_by=owner, event_key="order-a-payment",
            title="核对订单 A 到账", content="订单 A 到账待核实。",
            status=Event.Status.OPEN,
        )
        EventEvidence.objects.create(event=existing, message=anchor, created_by=owner)
    current = add_message(
        conversation, 2, "我说的是订单 A，今天核对到账。", reply_to=anchor,
    )
    output = clarify(
        current, anchor, [candidate.pk, candidate.pk], action=action,
        key=existing.event_key if existing else "",
    )

    def before_publish():
        candidate.refresh_from_db()
        assert candidate.status == DeferredEventCandidate.Status.PENDING
        assert candidate.resolved_event_id is None
        assert Event.objects.filter(space=space).count() == int(existing is not None)

    payload = analyze(chat, current, [output], before_publish=before_publish)
    presented = next(item for item in payload["deferred_candidates"] if item["id"] == candidate.pk)
    assert presented["anchor_seq"] == anchor.ingest_seq
    assert presented["text"] == ANCHOR_TEXT
    assert presented["reason"] == "ambiguous_target"
    assert presented["question"] == QUESTION

    candidate.refresh_from_db()
    event = Event.objects.get(space=space)
    if existing:
        assert event.pk == existing.pk
    assert candidate.status == DeferredEventCandidate.Status.RESOLVED
    assert candidate.resolved_event_id == event.pk
    assert set(event.evidence.values_list("message_id", flat=True)) == {anchor.pk, current.pk}
    assert DeferredEventCandidate.objects.filter(message=anchor).count() == 1

    replay = add_message(conversation, 3, "已说明是订单 A。", reply_to=anchor)
    replay_payload = analyze(chat, replay, [])
    assert candidate.pk not in [item["id"] for item in replay_payload["deferred_candidates"]]
    candidate.refresh_from_db()
    assert candidate.status == DeferredEventCandidate.Status.RESOLVED
    assert candidate.resolved_event_id == event.pk
    assert Event.objects.filter(space=space).count() == 1


@pytest.mark.parametrize("scenario", ["silence", "ack", "unrelated", "unknown_id", "no_anchor"])
def test_pending_candidate_is_not_confirmed_without_grounded_clarification(
    chat, analyze, scenario,
):
    _, space, conversation = chat
    anchor, candidate = defer_first(chat, analyze)
    actual_text = {
        "silence": "今天先休息。",
        "ack": "好的。",
        "unrelated": "今天请准备订单 C 的交付。",
        "unknown_id": "我说的是订单 A。",
        "no_anchor": "请财务今天核对订单 A。",
    }[scenario]
    current = add_message(conversation, 2, actual_text, reply_to=anchor)
    output = clarify(current, anchor, [candidate.pk])
    if scenario == "silence":
        events = []
    elif scenario == "ack":
        output["sources"][0]["role"] = "confirmation"
        events = [output]
    elif scenario == "unrelated":
        output["title"] = "准备订单 C 交付"
        output["summary"] = actual_text
        output["sources"] = output["sources"][:1]
        output.pop("resolves_deferred_ids")
        events = [output]
    elif scenario == "unknown_id":
        output["resolves_deferred_ids"] = [candidate.pk + 1]
        events = [output]
    else:
        output["sources"][1]["role"] = "matter"
        events = [output]

    analyze(chat, current, events)
    candidate.refresh_from_db()
    assert candidate.status == DeferredEventCandidate.Status.PENDING
    assert candidate.resolved_event_id is None
    assert candidate.resolution_suggestion_id is None
    if scenario in ("silence", "ack"):
        assert not Event.objects.filter(space=space).exists()
    elif scenario == "unrelated":
        event = Event.objects.get(space=space)
        assert event.title == output["title"]
        assert set(event.evidence.values_list("message_id", flat=True)) == {current.pk}


@pytest.mark.parametrize("different_space", [False, True], ids=["other-chat", "other-space"])
def test_foreign_candidate_is_not_exposed_or_resolved(chat, analyze, different_space):
    owner, space, _ = chat
    foreign_anchor, foreign_candidate = defer_first(chat, analyze)
    if different_space:
        space = make_space(owner, "other-deferred-space")
    conversation = make_conversation(space, "separate-payments", "另外的付款讨论")
    local_anchor = add_message(conversation, 1, "本群的订单 A 等待到账。")
    current = add_message(conversation, 2, "我说的是订单 A。", reply_to=local_anchor)
    payload = analyze(
        (owner, space, conversation), current,
        [clarify(current, local_anchor, [foreign_candidate.pk])],
    )

    assert all(item["id"] != foreign_candidate.pk for item in payload["deferred_candidates"])
    foreign_candidate.refresh_from_db()
    assert foreign_candidate.status == DeferredEventCandidate.Status.PENDING
    assert foreign_candidate.resolution_suggestion_id is None
    assert foreign_candidate.resolved_event_id is None
    assert not EventEvidence.objects.filter(message=foreign_anchor).exists()


def test_manual_dismissal_wins_before_reservation(chat, analyze, monkeypatch):
    _, space, conversation = chat
    anchor, candidate = defer_first(chat, analyze)
    current = add_message(conversation, 2, "我说的是订单 A。", reply_to=anchor)
    reserve = execution.reserve_resolutions

    def dismiss_then_reserve(**kwargs):
        DeferredEventCandidate.objects.filter(pk=candidate.pk).update(
            status=DeferredEventCandidate.Status.DISMISSED,
        )
        return reserve(**kwargs)

    monkeypatch.setattr(execution, "reserve_resolutions", dismiss_then_reserve)
    analyze(chat, current, [clarify(current, anchor, [candidate.pk])])

    candidate.refresh_from_db()
    assert candidate.status == DeferredEventCandidate.Status.DISMISSED
    assert not Event.objects.filter(space=space).exists()
    assert EventSuggestion.objects.get(space=space).status == EventSuggestion.Status.REJECTED


def test_manual_dismissal_wins_over_staged_publication(chat, analyze):
    _, space, conversation = chat
    anchor, candidate = defer_first(chat, analyze)
    current = add_message(conversation, 2, "我说的是订单 A。", reply_to=anchor)
    dismissed = False

    def dismiss_before_publish():
        nonlocal dismissed
        candidate.refresh_from_db()
        assert candidate.resolution_suggestion_id is not None
        candidate.status = DeferredEventCandidate.Status.DISMISSED
        candidate.save(update_fields=("status",))
        dismissed = True

    analyze(chat, current, [clarify(current, anchor, [candidate.pk])],
            before_publish=dismiss_before_publish)
    if dismissed:
        candidate.refresh_from_db()
        assert candidate.status == DeferredEventCandidate.Status.DISMISSED
        assert not Event.objects.filter(space=space).exists()
        assert candidate.resolution_suggestion.status == EventSuggestion.Status.REJECTED


def test_reprocessing_same_message_does_not_reopen_terminal_candidate(
    chat, analyze, monkeypatch,
):
    owner, space, conversation = chat
    anchor, candidate = defer_first(chat, analyze)
    # Replay via an immediate job so the scheduled exact assignment's unique
    # message reservation remains intact.
    candidate.status = DeferredEventCandidate.Status.DISMISSED
    candidate.save(update_fields=("status",))
    immediate_job = make_job(space, owner, conversation, end_seq=1, key="replay-anchor")
    run_job(immediate_job, monkeypatch, [defer(1)], [])

    assert immediate_job.state == AnalysisJob.State.READY, immediate_job.error
    candidate.refresh_from_db()
    assert candidate.status == DeferredEventCandidate.Status.DISMISSED
    assert candidate.resolved_event_id is None
    assert DeferredEventCandidate.objects.filter(message=anchor).count() == 1
    assert not Event.objects.filter(space=space).exists()

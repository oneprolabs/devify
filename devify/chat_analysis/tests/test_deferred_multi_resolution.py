"""Verify independent clarifications targeting one event in one chunk."""

import pytest
from django.utils import timezone

from chat_analysis import execution
from chat_analysis.models import (
    AnalysisJob,
    AnalysisJobMessage,
    DeferredEventCandidate,
    Event,
    EventEvidence,
)

from .test_deferred_events import chat as chat_fixture
from .test_deferred_events import clarify
from .test_event_extraction import add_message, make_job, run_job

chat = chat_fixture
pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(
    "scheduled", [False, True], ids=["immediate", "scheduled"]
)
@pytest.mark.parametrize(
    "second_has_evidence",
    [True, False],
    ids=["both-valid", "second-invalid"],
)
def test_two_attach_outputs_keep_each_candidates_own_evidence(
    chat,
    monkeypatch,
    scheduled,
    second_has_evidence,
):
    owner, space, conversation = chat
    original = add_message(conversation, 1, "跟进订单 A 的两笔退款。")
    event = Event.objects.create(
        space=space,
        created_by=owner,
        event_key="order-a-refunds",
        title="订单 A 退款核对",
        content="待核对两笔退款。",
        status=Event.Status.OPEN,
    )
    EventEvidence.objects.create(
        event=event, message=original, created_by=owner
    )
    first_anchor = add_message(
        conversation, 2, "上午提到的这笔退款，到底是哪张回执？"
    )
    second_anchor = add_message(
        conversation, 3, "下午提到的另一笔退款，是哪个流水号？"
    )
    first_candidate, second_candidate = [
        DeferredEventCandidate.objects.create(
            space=space,
            conversation=conversation,
            message=anchor,
            reason=DeferredEventCandidate.Reason.AMBIGUOUS_TARGET,
            question=question,
        )
        for anchor, question in (
            (first_anchor, "第一笔是哪张回执？"),
            (second_anchor, "第二笔是哪个流水号？"),
        )
    ]
    first = add_message(
        conversation,
        4,
        "订单 A 第一笔是回执 R-41，到账 60 元。",
        reply_to=first_anchor,
    )
    second = add_message(
        conversation,
        5,
        "订单 A 第二笔是流水 R-52，到账 80 元。",
        reply_to=second_anchor if second_has_evidence else None,
    )
    first_output = clarify(
        first,
        first_anchor,
        [first_candidate.pk],
        action="attach",
        key=event.event_key,
    )
    first_output.update(
        summary="第一笔回执 R-41，到账 60 元。", event_change="material"
    )
    second_output = clarify(
        second,
        second_anchor,
        [second_candidate.pk],
        action="attach",
        key=event.event_key,
    )
    second_output.update(
        summary="第二笔流水 R-52，到账 80 元。", event_change="material"
    )
    if not second_has_evidence:
        # An offered ID alone is not enough: neither citation nor direct reply
        # links this output to the second candidate's original message.
        second_output["sources"] = second_output["sources"][:1]

    job = make_job(space, owner, conversation, end_seq=second.ingest_seq)
    job.start_seq = second_anchor.ingest_seq
    if scheduled:
        job.specification.update(
            scheduled_message_scope=True,
            boundary=timezone.now().isoformat(),
        )
        for message in (first, second):
            AnalysisJobMessage.objects.create(job=job, message=message)
    job.save(update_fields=("start_seq", "specification"))
    captured = run_job(job, monkeypatch, [first_output, second_output], [])
    assert job.state == AnalysisJob.State.READY, job.error
    ((_, payload),) = captured
    assert [item["seq"] for item in payload["messages"]] == [
        first.ingest_seq,
        second.ingest_seq,
    ]
    assert {item["id"] for item in payload["deferred_candidates"]} == {
        first_candidate.pk,
        second_candidate.pk,
    }

    if scheduled:
        first_candidate.refresh_from_db()
        second_candidate.refresh_from_db()
        assert (
            first_candidate.status
            == second_candidate.status
            == DeferredEventCandidate.Status.PENDING
        )
        assert set(event.evidence.values_list("message_id", flat=True)) == {
            original.pk
        }
        execution.publish_ready_event_batches()

    assert Event.objects.get(space=space).pk == event.pk
    first_candidate.refresh_from_db()
    second_candidate.refresh_from_db()
    assert first_candidate.status == DeferredEventCandidate.Status.RESOLVED
    assert first_candidate.resolved_event_id == event.pk
    evidence_ids = set(event.evidence.values_list("message_id", flat=True))
    assert {original.pk, first_anchor.pk, first.pk} <= evidence_ids
    if second_has_evidence:
        assert (
            second_candidate.status == DeferredEventCandidate.Status.RESOLVED
        )
        assert second_candidate.resolved_event_id == event.pk
        assert evidence_ids == {
            original.pk,
            first_anchor.pk,
            first.pk,
            second_anchor.pk,
            second.pk,
        }
    else:
        assert second_candidate.status == DeferredEventCandidate.Status.PENDING
        assert second_candidate.resolved_event_id is None
        assert second_candidate.resolution_suggestion_id is None
        assert second_anchor.pk not in evidence_ids

import json

import pytest
from django.contrib.auth.models import User

from chat_analysis.services import add_note_evidence, create_note
from chat_analysis.suggestions import create_event_suggestion
from chat_analysis.tests.test_event_extraction import (
    add_message,
    make_conversation,
    make_job,
    make_space,
)


@pytest.fixture
def candidates():
    owner = User.objects.create_user(username="event-reducer")
    space = make_space(owner, "event-reducer")
    conversation = make_conversation(space, "support", "Support")
    messages = [
        add_message(conversation, 1, "Case PR-55 requested a refund."),
        add_message(conversation, 2, "Case PR-55 refund completed."),
        add_message(conversation, 3, "Case PR-56 requested a refund."),
        add_message(conversation, 4, "Office Wi-Fi password changed."),
    ]
    job = make_job(space, owner, conversation, end_seq=4)
    suggestions = []
    for index, message in enumerate(messages[:3]):
        note = create_note(
            actor=owner,
            space=space,
            analysis_job=job,
            note_key=f"note-{index}",
            title="Refund case",
            content=message.parts.first().text,
        )
        add_note_evidence(actor=owner, note=note, message=message)
        add_note_evidence(actor=owner, note=note, message=messages[3])
        suggestions.append(
            create_event_suggestion(
                actor=owner,
                note=note,
                analysis_job=job,
                event_key=f"chunk-{index}",
                entity_key="refunds",
                title="Refund case",
                summary=f"Refund case update {index}",
                status="open",
                source_seqs=[message.ingest_seq],
            )
        )
    return job, suggestions


@pytest.mark.django_db
def test_reduction_uses_only_cited_sources(candidates):
    from chat_analysis.event_reducer import prepare_event_reduction

    job, suggestions = candidates

    def decide(**request):
        items = json.loads(request["content"])["candidates"]
        assert [item["evidence"][0]["text"] for item in items] == [
            "Case PR-55 requested a refund.",
            "Case PR-55 refund completed.",
            "Case PR-56 requested a refund.",
        ]
        assert "Wi-Fi" not in request["content"]
        return {"groups": [[0, 1]]}

    assert prepare_event_reduction(job, suggestions, call_json=decide) == [
        suggestions[:2],
        suggestions[2:],
    ]


@pytest.mark.django_db
def test_reduction_keeps_citations_distinct_across_conversations(candidates):
    from chat_analysis.event_reducer import prepare_event_reduction

    job, suggestions = candidates
    conversation = make_conversation(job.space, "billing", "Billing")
    billing_job = make_job(
        job.space, job.created_by, conversation, end_seq=2, key="billing"
    )
    request = add_message(conversation, 1, "Case PR-55 requested a refund.")
    # Both chats have ingest sequence 2, including on this note's evidence.
    reply = add_message(
        conversation,
        2,
        "Billing finalized the Case PR-55 refund.",
        reply_to=request,
    )
    note = create_note(
        actor=job.created_by,
        space=job.space,
        analysis_job=billing_job,
        note_key="billing-note",
        title="Refund completion",
        content="Billing processed the refund.",
    )
    add_note_evidence(actor=job.created_by, note=note, message=reply)
    original = suggestions[1].note.evidence.get(message__ingest_seq=2).message
    add_note_evidence(actor=job.created_by, note=note, message=original)
    billing = create_event_suggestion(
        actor=job.created_by,
        note=note,
        analysis_job=billing_job,
        event_key="billing",
        title="Refund completion",
        summary=note.content,
        source_seqs=[2],
    )

    def decide(**kwargs):
        first, second = json.loads(kwargs["content"])["candidates"]
        (original_evidence,) = first["evidence"]
        (billing_evidence,) = second["evidence"]
        assert original_evidence["seq"] == billing_evidence["seq"] == 2
        assert original_evidence["conversation_id"] == job.conversation_id
        assert original_evidence["message_id"] == original.pk
        assert billing_evidence["conversation_id"] == conversation.pk
        assert billing_evidence["message_id"] == reply.pk
        assert billing_evidence["reply_to_message_id"] == request.pk
        assert (
            billing_evidence["text"]
            == "Billing finalized the Case PR-55 refund."
        )
        return {"groups": [[0, 1]]}

    assert prepare_event_reduction(
        job,
        [suggestions[1], billing],
        call_json=decide,
    ) == [[suggestions[1], billing]]


@pytest.mark.django_db
def test_overlapping_or_invalid_groups_preserve_candidates(candidates):
    from chat_analysis.event_reducer import prepare_event_reduction

    job, suggestions = candidates

    def decide(**request):
        return {"groups": [[0, 1], [1, 2], [0, 4], [True, 2], [0, 0]]}

    assert prepare_event_reduction(job, suggestions, call_json=decide) == [
        [suggestion] for suggestion in suggestions
    ]


@pytest.mark.django_db
def test_reduction_uses_the_cited_message_fragment(candidates):
    from chat_analysis.event_reducer import prepare_event_reduction

    job, suggestions = candidates
    note = suggestions[1].note
    message = note.evidence.get(message__ingest_seq=2).message
    part = message.parts.get()
    original = part.text
    prefix = "An unrelated topic. " * 40
    part.text = prefix + original
    part.save(update_fields=["text"])
    note.note_key = f"job:{job.uuid}:2-2:offset:{len(prefix)}-{len(part.text)}"
    note.save(update_fields=["note_key"])

    def decide(**request):
        item = json.loads(request["content"])["candidates"][1]
        assert item["evidence"][0]["text"] == original
        return {"groups": [[0, 1]]}

    assert prepare_event_reduction(job, suggestions, call_json=decide) == [
        suggestions[:2],
        suggestions[2:],
    ]


def test_reduction_links_candidates_across_batches(monkeypatch):
    from chat_analysis import event_reducer

    suggestions = list(range(9))
    payloads = [
        {
            "title": "Case PR-55" if index in (1, 8) else f"Case {index}",
            "summary": "Refund case update",
            "entity": "refunds",
            "evidence": [{"text": f"Message {index}"}],
        }
        for index in suggestions
    ]
    monkeypatch.setattr(
        event_reducer,
        "_candidate_payloads",
        lambda job, suggestions: payloads,
    )

    def decide(**request):
        items = json.loads(request["content"])["candidates"]
        assert len(items) <= 8
        same_case = [
            item["index"] for item in items if item["title"] == "Case PR-55"
        ]
        return {"groups": [same_case] if len(same_case) > 1 else []}

    assert event_reducer.prepare_event_reduction(
        None, suggestions, call_json=decide
    ) == [[0], [1, 8], [2], [3], [4], [5], [6], [7]]


def test_compact_reduction_preserves_stable_ids_for_group_excerpts(
    monkeypatch,
):
    from chat_analysis import event_reducer

    def excerpt(index):
        return {
            "message_id": index + 10,
            "reply_to_message_id": 10 if index == 1 else None,
            "conversation_id": 100 if index < 2 else 200,
            "seq": 1,
            "text": "Example " * 30,
        }

    suggestions = list(range(9))
    payloads = [
        {
            "title": f"Candidate {index}",
            "summary": "",
            "entity": "refunds",
            "evidence": [excerpt(index)],
        }
        for index in suggestions
    ]
    monkeypatch.setattr(
        event_reducer,
        "_candidate_payloads",
        lambda job, suggestions: payloads,
    )
    seen = []

    def decide(**request):
        items = json.loads(request["content"])["candidates"]
        seen.append(items)
        if len(seen) == 1:
            return {"groups": [[0, 1]]}
        (initial,) = items[0]["evidence"]
        (latest,) = items[0]["latest_evidence"]
        assert initial == {**excerpt(0), "text": excerpt(0)["text"][:120]}
        assert latest == {**excerpt(1), "text": excerpt(1)["text"][:120]}
        return {"groups": []}

    assert event_reducer.prepare_event_reduction(
        None, suggestions, call_json=decide
    ) == [[0, 1], [2], [3], [4], [5], [6], [7], [8]]
    assert len(seen) == 2

"""Keep deferred-event evidence and human decisions across message deduplication."""

import pytest
from django.contrib.auth.models import User

from chat_analysis.models import DeferredEventCandidate, Event, EventSuggestion, Note
from chat_analysis.tests.test_event_extraction import make_conversation, make_job, make_space
from chat_domain.models import Message
from chat_domain.services import consolidate_conversation_messages, merge_messages

pytestmark = pytest.mark.django_db


@pytest.fixture
def world():
    owner = User.objects.create_user(username="deferred-merge-owner")
    space = make_space(owner, "deferred-merge")
    conversation = make_conversation(space, "merge-chat", "Merge chat")
    source = Message.objects.create(
        conversation=conversation, message_key="fallback:1", ingest_seq=1,
        content_fingerprint="same-content",
    )
    target = Message.objects.create(
        conversation=conversation, message_key="srv:2", ingest_seq=2,
        content_fingerprint="same-content",
    )
    return owner, space, conversation, source, target


def make_candidate(message, **fields):
    return DeferredEventCandidate.objects.create(
        space_id=message.conversation.space_id,
        conversation=message.conversation, message=message,
        reason=DeferredEventCandidate.Reason.AMBIGUOUS_TARGET,
        question="Which order?", **fields,
    )


def make_suggestion(owner, space, conversation, key, seqs, **fields):
    job = make_job(space, owner, conversation, end_seq=3, key=key)
    note = Note.objects.create(
        space=space, analysis_job=job, created_by=owner,
        note_key=key, title="Clarification",
    )
    return EventSuggestion.objects.create(
        space=space, analysis_job=job, note=note, created_by=owner,
        event_key=key, title="Clarification", summary="The order is now known.",
        source_seqs=seqs, **fields,
    )


@pytest.mark.parametrize("status", ["pending", "dismissed", "resolved"])
def test_merge_rehomes_candidate_and_pending_citations(world, status):
    owner, space, conversation, source, target = world
    other = make_conversation(space, "other-chat", "Other chat")
    pending = make_suggestion(owner, space, conversation, "pending", ["001", "2", 3, 1])
    accepted = make_suggestion(owner, space, conversation, "accepted", [1], status="accepted")
    outside = make_suggestion(owner, space, other, "outside", [1])
    event = Event.objects.create(space=space, created_by=owner, event_key="order", title="Order")
    candidate = make_candidate(
        source, status=status, resolution_suggestion=pending,
        resolved_event=event if status == "resolved" else None,
    )

    source_id = source.pk
    assert merge_messages(source=source, target=target).pk == target.pk

    candidate.refresh_from_db()
    assert candidate.message_id == target.pk
    assert candidate.status == status
    assert candidate.resolved_event_id == (event.pk if status == "resolved" else None)
    assert candidate.resolution_suggestion_id == pending.pk
    assert not Message.objects.filter(pk=source_id).exists()
    pending.refresh_from_db()
    accepted.refresh_from_db()
    outside.refresh_from_db()
    assert pending.source_seqs == [2, 3]
    assert accepted.source_seqs == [1]
    assert outside.source_seqs == [1]


def test_merge_prefers_manual_disposition_and_rejects_duplicate_reservations(world):
    owner, space, conversation, source, target = world
    proposal = make_suggestion(owner, space, conversation, "proposal", [2, 3])
    manual = make_candidate(source, status=DeferredEventCandidate.Status.DISMISSED)
    duplicate = make_candidate(target, resolution_suggestion=proposal)
    extra_message = Message.objects.create(
        conversation=conversation, message_key="srv:3", ingest_seq=3,
    )
    extra = make_candidate(extra_message, resolution_suggestion=proposal)

    assert merge_messages(source=source, target=target).pk == target.pk

    manual.refresh_from_db()
    proposal.refresh_from_db()
    extra.refresh_from_db()
    assert manual.message_id == target.pk
    assert manual.status == DeferredEventCandidate.Status.DISMISSED
    assert not DeferredEventCandidate.objects.filter(pk=duplicate.pk).exists()
    assert proposal.status == EventSuggestion.Status.REJECTED
    assert extra.status == DeferredEventCandidate.Status.PENDING
    assert extra.resolution_suggestion_id is None


def test_consolidation_keeps_both_conflicting_final_decisions(world):
    owner, space, conversation, source, target = world
    event = Event.objects.create(space=space, created_by=owner, event_key="order", title="Order")
    proposal = make_suggestion(owner, space, conversation, "stale", [1])
    unrelated = make_suggestion(owner, space, conversation, "unrelated", [1])
    dismissed = make_candidate(
        source, status=DeferredEventCandidate.Status.DISMISSED,
        resolution_suggestion=proposal,
    )
    resolved = make_candidate(
        target, status=DeferredEventCandidate.Status.RESOLVED, resolved_event=event,
    )

    assert consolidate_conversation_messages(conversation) == []

    proposal.refresh_from_db()
    unrelated.refresh_from_db()
    assert proposal.status == EventSuggestion.Status.REJECTED
    assert unrelated.source_seqs == [1]
    dismissed.refresh_from_db()
    resolved.refresh_from_db()
    assert (dismissed.message_id, dismissed.status) == (source.pk, "dismissed")
    assert (resolved.message_id, resolved.status, resolved.resolved_event_id) == (target.pk, "resolved", event.pk)
    assert Message.objects.filter(pk__in=(source.pk, target.pk)).count() == 2

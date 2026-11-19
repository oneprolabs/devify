"""Verify deferred event clarification across two real chat uploads."""

import json
from datetime import timedelta

import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone

from chat_analysis.execution import publish_ready_event_batches
from chat_analysis.models import AnalysisJob, DeferredEventCandidate, Event
from chat_domain.models import Conversation, Message, MessageOrigin
from chat_ingestion.models import UploadBatch
from chat_ingestion.tests.archives import DEFAULT_MESSAGES, build_archive
from chat_ingestion.tests.test_content_dedup import upload
from core.tracking import LLMTracker

from .test_e2e_chain import chain as chain_fixture
from .test_e2e_chain import (
    client_for,
    make_space,
    run_scheduled_analysis,
)

chain = chain_fixture

pytestmark = [pytest.mark.django_db, pytest.mark.integration]


def alert_archive(index, text):
    message = DEFAULT_MESSAGES[index - 1]
    return build_archive(
        messages=[message],
        parts=[
            {
                "conversation_id": message["conversation_id"],
                "message_key": message["message_key"],
                "part_key": "p0",
                "kind": "text",
                "ordinal": 0,
                "text": text,
            }
        ],
        media={},
    )


def test_uploaded_clarification_resolves_deferred_event(settings, monkeypatch):
    settings.CHAT_ANALYSIS_AUTO_CREATE_EVENTS = True
    owner = User.objects.create_user(username="deferred-upload-owner")
    space = make_space(owner, slug="deferred-upload-team")
    client = client_for(owner)
    review_url = reverse("chat-deferred-event-candidate-list", args=[space.pk])
    original_text = (
        "今天下班前只核对其中一笔退款，暂时分不清是订单 A 还是订单 B。"
    )
    clarification_text = "刚才说的是订单 A 的退款，今天下班前核对它是否到账。"
    original_seq = None
    candidate_id = None
    clarification_seq = None

    def model(*, node_name, content, **_kwargs):
        if node_name == "chat_note_structuring":
            return {"facts": []}, {}
        assert node_name == "chat_event_extraction"
        payload = json.loads(content)
        (current,) = payload["messages"]
        if candidate_id is None:
            assert (current["seq"], current["text"]) == (
                original_seq,
                original_text,
            )
            return {
                "events": [
                    {
                        "action": "defer",
                        "defer_reason": "ambiguous_target",
                        "followup_signal": "deadline",
                        "followup_question": "要核对的是订单 A 还是订单 B？",
                        "sources": [{"seq": current["seq"], "role": "matter"}],
                    }
                ]
            }, {}
        assert (current["seq"], current["text"]) == (
            clarification_seq,
            clarification_text,
        )
        assert [
            (item["id"], item["anchor_seq"], item["text"])
            for item in payload["deferred_candidates"]
        ] == [(candidate_id, original_seq, original_text)]
        return {
            "events": [
                {
                    "action": "create",
                    "title": "核对订单 A 退款到账",
                    "summary": clarification_text,
                    "status": "open",
                    "status_scope": "event",
                    "context_decision": "independent",
                    "target_resolution": "resolved",
                    "new_event_basis": "explicit_work",
                    "basis_seqs": [current["seq"]],
                    "resolves_deferred_ids": [candidate_id],
                    "sources": [
                        {"seq": current["seq"], "role": "matter"},
                        {"seq": original_seq, "role": "background"},
                    ],
                }
            ]
        }, {}

    monkeypatch.setattr(LLMTracker, "call_and_track", model)

    first = upload(
        client, space, "deferred-first", alert_archive(1, original_text)
    )
    assert first.status == UploadBatch.Status.COMPLETED
    assert first.message_count == 1
    conversation = Conversation.objects.get(space=space)
    original = Message.objects.get(
        conversation=conversation, message_key="srv:1"
    )
    assert MessageOrigin.objects.filter(
        message=original, upload_item__batch=first
    ).exists()
    original_seq = original.ingest_seq
    assert not AnalysisJob.objects.filter(space=space).exists()

    assert (
        run_scheduled_analysis(conversation).job.state
        == AnalysisJob.State.READY
    )
    assert publish_ready_event_batches() == 0
    candidate = DeferredEventCandidate.objects.get(
        message=original, space=space
    )
    assert candidate.status == DeferredEventCandidate.Status.PENDING
    assert candidate.urgent
    assert not Event.objects.filter(space=space).exists()
    candidate_id = candidate.pk
    # Advance review eligibility without waiting or changing the upload clock.
    DeferredEventCandidate.objects.filter(pk=candidate_id).update(
        created_at=timezone.now() - timedelta(minutes=31),
    )
    response = client.get(review_url)
    assert response.status_code == 200, response.data
    (row,) = response.data["data"]["list"]
    assert row["id"] == candidate_id
    assert row["source"]["message_id"] == original.pk

    second = upload(
        client,
        space,
        "deferred-second",
        alert_archive(2, clarification_text),
    )
    assert second.pk != first.pk
    assert second.status == UploadBatch.Status.COMPLETED
    assert second.message_count == 1
    clarification = Message.objects.get(
        conversation=conversation, message_key="srv:2"
    )
    assert MessageOrigin.objects.filter(
        message=clarification,
        upload_item__batch=second,
    ).exists()
    clarification_seq = clarification.ingest_seq
    assert clarification_seq > original_seq

    assert (
        run_scheduled_analysis(conversation).job.state
        == AnalysisJob.State.READY
    )
    candidate.refresh_from_db()
    assert candidate.status == DeferredEventCandidate.Status.PENDING
    assert candidate.resolved_event_id is None
    assert not Event.objects.filter(space=space).exists()

    assert publish_ready_event_batches() == 1
    event = Event.objects.get(space=space)
    assert event.status == Event.Status.OPEN
    assert event.title == "核对订单 A 退款到账"
    assert set(event.evidence.values_list("message_id", flat=True)) == {
        original.pk,
        clarification.pk,
    }
    candidate.refresh_from_db()
    assert candidate.status == DeferredEventCandidate.Status.RESOLVED
    assert candidate.resolved_event_id == event.pk
    assert not DeferredEventCandidate.objects.filter(
        message=clarification
    ).exists()
    response = client.get(review_url)
    assert response.status_code == 200, response.data
    assert response.data["data"]["list"] == []
    assert publish_ready_event_batches() == 0

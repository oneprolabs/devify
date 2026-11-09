from unittest.mock import patch

import pytest
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.test import APIClient

from chat_analysis.models import (
    AnalysisJob,
    Conversation,
    Event,
    EventSuggestion,
    Note,
)
from chat_domain.models import Message, MessagePart
from spaces.models import Space, SpaceMembership

pytestmark = pytest.mark.django_db


def make_space(owner, slug):
    space = Space.objects.create(
        name=slug, slug=slug, kind=Space.Kind.TEAM, owner=owner
    )
    SpaceMembership.objects.create(
        space=space, user=owner, role=SpaceMembership.Role.OWNER
    )
    return space


def make_job(space, owner):
    conversation = Conversation.objects.create(
        space=space,
        platform=Conversation.Platform.WECHAT,
        source_namespace="test",
        source_conversation_id="group",
        identity_key=f"wechat:test:group-{space.pk}",
    )
    return AnalysisJob.objects.create(
        space=space,
        created_by=owner,
        conversation=conversation,
        request_key=f"job-{space.pk}",
        end_seq=1,
        input_version="wechat.v1",
    )


def test_event_suggestion_accept_creates_event_and_note_link():
    owner = User.objects.create_user(username="suggestion-owner")
    space = make_space(owner, "suggestion-team")
    job = make_job(space, owner)
    note = Note.objects.create(
        space=space,
        created_by=owner,
        note_key="note",
        title="Note",
        content="Content",
    )
    suggestion = EventSuggestion.objects.create(
        space=space,
        analysis_job=job,
        note=note,
        event_key="event-suggestion",
        title="Follow up",
        summary="Prepare a quote.",
        created_by=owner,
    )
    client = APIClient()
    client.force_authenticate(user=owner)

    response = client.post(
        f"/api/v1/event-suggestions/{suggestion.pk}/review",
        {"decision": "accepted"},
        format="json",
    )

    assert response.status_code == 200
    suggestion.refresh_from_db()
    assert suggestion.status == EventSuggestion.Status.ACCEPTED
    assert suggestion.event_id
    assert Event.objects.filter(pk=suggestion.event_id).exists()
    assert suggestion.note.event_links.filter(
        event_id=suggestion.event_id
    ).exists()


def test_llm_note_structuring_creates_pending_event_suggestion(settings):
    owner = User.objects.create_user(username="suggestion-llm-owner")
    space = make_space(owner, "suggestion-llm-team")
    job = make_job(space, owner)
    message = Message.objects.create(
        conversation=job.conversation,
        message_key="src:1",
        ingest_seq=1,
        sender_name="Alice",
    )
    MessagePart.objects.create(
        message=message,
        part_key="text-0",
        kind=MessagePart.Kind.TEXT,
        text="Please prepare the annual quote.",
    )
    settings.CHAT_ANALYSIS_LLM_ENABLED = True
    settings.CHAT_ANALYSIS_AUTO_CREATE_EVENTS = False
    result = {
        "facts": ["Annual quote requested"],
        "actions": ["Prepare quote"],
        "risks": [],
        "decisions": [],
        "events": [
            {
                "event_key": "quote-follow-up",
                "title": "Prepare quote",
                "summary": "Prepare the annual quote.",
            }
        ],
    }
    with patch(
        "chat_analysis.execution.LLMTracker.call_and_track",
        return_value=(result, {"model": "test"}),
    ):
        from chat_analysis.execution import execute_analysis_job

        execution = execute_analysis_job(job.pk, worker_id="suggestion-test")

    assert execution.job.state == AnalysisJob.State.READY
    assert (
        EventSuggestion.objects.filter(
            analysis_job=job, status=EventSuggestion.Status.PENDING
        ).count()
        == 1
    )
    assert Note.objects.filter(
        analysis_job=job, generation_version="chat-note-llm.v1"
    ).exists()


def test_auto_create_events_accepts_llm_suggestions(settings):
    owner = User.objects.create_user(username="suggestion-auto-owner")
    space = make_space(owner, "suggestion-auto-team")
    job = make_job(space, owner)
    message = Message.objects.create(
        conversation=job.conversation,
        message_key="src:2",
        ingest_seq=1,
        sender_name="Alice",
        occurred_at=timezone.now(),
    )
    MessagePart.objects.create(
        message=message,
        part_key="text-0",
        kind=MessagePart.Kind.TEXT,
        text="Please prepare the annual quote.",
    )
    settings.CHAT_ANALYSIS_LLM_ENABLED = True
    settings.CHAT_ANALYSIS_AUTO_CREATE_EVENTS = True
    result = {
        "facts": ["Annual quote requested"],
        "actions": ["Prepare quote"],
        "risks": [],
        "decisions": [],
        "events": [
            {
                "event_key": "quote-follow-up",
                "title": "Prepare quote",
                "summary": "Prepare the annual quote.",
            }
        ],
    }
    with patch(
        "chat_analysis.execution.LLMTracker.call_and_track",
        return_value=(result, {"model": "test"}),
    ):
        from chat_analysis.execution import execute_analysis_job

        execution = execute_analysis_job(
            job.pk, worker_id="suggestion-auto-test"
        )

    assert execution.job.state == AnalysisJob.State.READY
    suggestion = EventSuggestion.objects.get(analysis_job=job)
    assert suggestion.status == EventSuggestion.Status.ACCEPTED
    event = Event.objects.get(space=space, event_key="quote-follow-up")
    assert suggestion.event_id == event.pk
    assert event.last_activity_at == message.occurred_at
    note = Note.objects.get(analysis_job=job)
    assert note.event_links.filter(event=event).exists()

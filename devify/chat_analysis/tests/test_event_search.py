from datetime import timedelta

import pytest
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.test import APIClient

from chat_analysis.models import (
    AnalysisJob,
    Event,
    EventEvidence,
    EventNote,
    EventParticipantEvidence,
    EventSuggestion,
    EventTag,
    EventTagAssignment,
    Note,
    NoteEvidence,
)
from chat_analysis.tests.test_event_extraction import (
    make_conversation,
    make_space,
)
from chat_domain.models import ConversationIdentity, Message
from spaces.models import SpaceAuditLog, SpaceTakeover
from spaces.services import SpaceBootstrapService

pytestmark = [pytest.mark.django_db, pytest.mark.integration]


@pytest.fixture
def event_list():
    owner = User.objects.create_user(username="event-search-owner")
    space = make_space(owner, "event-search")
    client = APIClient()
    client.force_authenticate(user=owner)
    return space, client, f"/api/v1/spaces/{space.pk}/events"


def create_event(space, key, title, **fields):
    return Event.objects.create(
        space=space, created_by=space.owner, event_key=key, title=title,
        **fields,
    )


def test_keyword_search_finds_events_beyond_the_first_page(event_list):
    space, client, path = event_list
    now = timezone.now()
    match = create_event(
        space, "release", "Plan Release42",
        last_activity_at=now - timedelta(days=1),
    )
    Event.objects.bulk_create([
        Event(
            space=space, created_by=space.owner, event_key=f"other-{index}",
            title="Other work", last_activity_at=now,
        )
        for index in range(50)
    ])

    unfiltered = client.get(path, {"page_size": 50})
    assert unfiltered.status_code == 200
    data = unfiltered.json()["data"]
    assert data["search_supported"] is True
    assert data["pagination"]["total"] == 51
    assert len(data["list"]) == 50
    assert match.pk not in {row["id"] for row in data["list"]}

    response = client.get(path, {"q": "  eLeAsE42\t", "page_size": 50})
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["search_supported"] is True
    assert data["pagination"]["total"] == 1
    assert [row["id"] for row in data["list"]] == [match.pk]


def test_keyword_search_treats_unicode_and_wildcards_as_text(event_list):
    space, client, path = event_list
    long_query = "字" * 200
    match = create_event(
        space, "literal", "Deployment",
        content=rf"批准发布R42 50%_\done {long_query}",
    )
    create_event(
        space, "decoy", "Decoy", content=r"批准发布R42 50xy\done",
    )

    for query in (r"发布r42 50%_\Done", f"  {long_query}  "):
        response = client.get(path, {"q": query})
        assert response.status_code == 200
        data = response.json()["data"]
        assert [row["id"] for row in data["list"]] == [match.pk]

    response = client.get(path, {"q": "不存在"})
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["list"] == []
    assert data["pagination"]["total"] == 0
    assert data["search_supported"] is True

    unfiltered = client.get(path).json()["data"]
    for query in ("", "\t \u3000"):
        response = client.get(path, {"q": query})
        assert response.status_code == 200
        assert response.json()["data"] == unfiltered

    response = client.get(path, {"q": long_query + "字"})
    assert response.status_code == 400
    assert "200" in response.json()["data"]["detail"]


def test_keyword_search_keeps_scoped_badges_and_filters_before_page_two(
    event_list,
):
    space, client, path = event_list
    owner = space.owner
    chat = make_conversation(space, "selected", "Selected conversation")
    ConversationIdentity.objects.create(
        conversation=chat, user=owner, sender_key="owner",
    )
    message = Message.objects.create(
        conversation=chat, message_key="message", ingest_seq=1,
        sender_key="owner",
    )
    note = Note.objects.create(
        space=space, created_by=owner, note_key="note", title="Work",
    )
    NoteEvidence.objects.create(note=note, message=message)
    job = AnalysisJob.objects.create(
        space=space, created_by=owner, conversation=chat, request_key="job",
        end_seq=1, input_version="wechat.v1",
    )
    tag = EventTag.objects.create(
        space=space, created_by=owner, tag_key="planned", label="Planned",
    )
    now = timezone.now()
    first = create_event(
        space, "first", "Release notes", status=Event.Status.OPEN,
        last_activity_at=now,
    )
    second = create_event(
        space, "second", "Test release", status=Event.Status.OPEN,
        last_activity_at=now,
    )
    nonmatch = create_event(
        space, "nonmatch", "Review design", status=Event.Status.OPEN,
        last_activity_at=now,
    )
    related = create_event(
        space, "related", "Release report", status=Event.Status.OPEN,
    )
    done = create_event(
        space, "done", "Release plan", status=Event.Status.DONE,
    )
    untagged = create_event(
        space, "untagged", "Release calendar", status=Event.Status.OPEN,
    )
    unlinked = create_event(
        space, "unlinked", "Release review", status=Event.Status.OPEN,
    )
    for event in (first, second, nonmatch, related, done, untagged):
        EventNote.objects.create(event=event, note=note, created_by=owner)
    for event in (first, second, nonmatch, related, done, unlinked):
        EventTagAssignment.objects.create(
            event=event, tag=tag, created_by=owner,
        )
    for event in (first, second, nonmatch, related):
        EventEvidence.objects.create(
            event=event, message=message, created_by=owner,
        )
    for event in (first, second, nonmatch):
        suggestion = EventSuggestion.objects.create(
            space=space, analysis_job=job, note=note, event=event,
            event_key=event.event_key, title=event.title,
            status=EventSuggestion.Status.ACCEPTED, created_by=owner,
        )
        EventParticipantEvidence.objects.create(
            suggestion=suggestion, message=message, sender_key="owner",
            state="open", reference="action",
        )

    scope = {
        "conversation_id": chat.pk, "status": "open", "tag_key": "planned",
        "q": "release",
    }
    expected_counts = {"my_todo": 3, "related": 1, "other": 0}
    response = client.get(path, {**scope, "include_relevance_counts": "true"})
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["relevance_counts"] == expected_counts
    assert data["pagination"]["total"] == 3

    response = client.get(
        path, {**scope, "viewer_relevance": "my_todo", "page_size": 1},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["relevance_counts"] == expected_counts
    assert data["pagination"]["total"] == 2
    assert [row["id"] for row in data["list"]] == [second.pk]

    response = client.get(data["pagination"]["next"])
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["pagination"]["page"] == 2
    assert data["pagination"]["total"] == 2
    assert data["relevance_counts"] == expected_counts
    assert [row["id"] for row in data["list"]] == [first.pk]


def test_keyword_search_respects_private_space_and_takeover_audit():
    owner = User.objects.create_user(username="event-search-private-owner")
    outsider = User.objects.create_user(username="event-search-outsider")
    admin = User.objects.create_user(
        username="event-search-admin", is_staff=True,
    )
    space = SpaceBootstrapService.ensure_personal_space(owner)
    event = create_event(space, "private", "Private release")
    client = APIClient()
    path = f"/api/v1/spaces/{space.pk}/events"
    for user in (outsider, admin):
        client.force_authenticate(user=user)
        assert client.get(path, {"q": "release"}).status_code == 404

    takeover = SpaceTakeover.objects.create(
        space=space, admin=admin, reason="Audit access",
    )
    response = client.get(path, {"q": "release"})
    assert response.status_code == 200
    assert [row["id"] for row in response.json()["data"]["list"]] == [event.pk]
    audit = SpaceAuditLog.objects.get(
        space=space, actor=admin, action="chat.event_list_viewed",
    )
    assert audit.metadata == {"takeover_id": takeover.pk}

from datetime import timedelta

import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from chat_analysis.models import DeferredEventCandidate, Event, EventEvidence
from chat_domain.models import Message, MessagePart
from spaces.models import SpaceAuditLog, SpaceMembership

from .test_api_resources import make_message, make_space

pytestmark = [pytest.mark.django_db, pytest.mark.integration]


def make_candidate(space, conversation, seq=2, *, age=31, **fields):
    message = Message.objects.create(
        conversation=conversation,
        message_key=f"candidate:{seq}",
        ingest_seq=seq,
        occurred_at=timezone.now(),
    )
    MessagePart.objects.create(
        message=message,
        part_key="text-1",
        kind=MessagePart.Kind.TEXT,
        ordinal=0,
        text="请今天确认付款。" + "长" * 240,
    )
    candidate = DeferredEventCandidate.objects.create(
        space=space,
        conversation=conversation,
        message=message,
        reason=DeferredEventCandidate.Reason.AMBIGUOUS_TARGET,
        question="要确认的是哪一笔？",
        **{"urgent": True, **fields},
    )
    DeferredEventCandidate.objects.filter(pk=candidate.pk).update(
        created_at=timezone.now() - timedelta(minutes=age),
    )
    return candidate


def review_url(space, candidate):
    return reverse(
        "chat-deferred-event-candidate-review", args=[space.pk, candidate.pk]
    )


@pytest.fixture
def world():
    owner = User.objects.create_user(username="deferred-owner")
    outsider = User.objects.create_user(username="deferred-outsider")
    space = make_space(owner, "deferred-team")
    foreign_space = make_space(outsider, "deferred-other")
    conversation = make_message(space).conversation
    client = APIClient()
    client.default_format = "json"
    client.force_authenticate(user=owner)
    return owner, outsider, space, foreign_space, conversation, client


def test_queue_lists_only_aged_urgent_pending_candidates(world):
    _, _, space, foreign_space, conversation, client = world
    candidate = make_candidate(space, conversation)
    make_candidate(space, conversation, 3, age=29)
    make_candidate(space, conversation, 4, urgent=False)
    make_candidate(
        space, conversation, 5, status=DeferredEventCandidate.Status.RESOLVED
    )
    make_candidate(
        space, conversation, 6, status=DeferredEventCandidate.Status.DISMISSED
    )
    orphan = make_candidate(space, conversation, 7)
    Message.objects.filter(pk=orphan.message_id).update(
        orphaned_at=timezone.now()
    )
    make_candidate(foreign_space, make_message(foreign_space).conversation)

    response = client.get(
        reverse("chat-deferred-event-candidate-list", args=[space.pk])
    )
    assert response.status_code == 200
    data = response.data["data"]
    assert data["pagination"]["total"] == 1
    (row,) = data["list"]
    assert row["id"] == candidate.pk
    assert row["reason"] == "ambiguous_target"
    assert row["question"] == "要确认的是哪一笔？"
    assert row["source"]["message_id"] == candidate.message_id
    assert row["source"]["conversation_id"] == conversation.pk
    assert row["source"]["excerpt"].startswith("请今天确认付款。")
    assert len(row["source"]["excerpt"]) == 240
    events = client.get(f"/api/v1/spaces/{space.pk}/events")
    assert events.status_code == 200
    assert events.data["data"]["list"] == []


def test_guest_can_read_but_not_review_and_outsider_cannot_access(world):
    _, outsider, space, _, conversation, client = world
    candidate = make_candidate(space, conversation)
    list_url = reverse("chat-deferred-event-candidate-list", args=[space.pk])
    client.force_authenticate(user=outsider)
    assert client.get(list_url).status_code == 404
    assert (
        client.post(
            review_url(space, candidate), {"decision": "dismiss"}
        ).status_code
        == 404
    )
    SpaceMembership.objects.create(
        space=space, user=outsider, role=SpaceMembership.Role.GUEST
    )
    assert client.get(list_url).status_code == 200
    assert (
        client.post(
            review_url(space, candidate), {"decision": "dismiss"}
        ).status_code
        == 403
    )
    candidate.refresh_from_db()
    assert candidate.status == DeferredEventCandidate.Status.PENDING


def test_link_requires_same_space_existing_event_and_preserves_its_state(
    world,
):
    owner, outsider, space, foreign_space, conversation, client = world
    candidate = make_candidate(space, conversation)
    foreign_event = Event.objects.create(
        space=foreign_space,
        created_by=outsider,
        event_key="other",
        title="Other",
    )
    event = Event.objects.create(
        space=space,
        created_by=owner,
        event_key="payment",
        title="付款",
        status=Event.Status.DONE,
        content="已核对",
        last_activity_at=timezone.now(),
    )
    url = review_url(space, candidate)
    assert client.post(url, {"decision": "link"}).status_code == 400
    assert (
        client.post(
            url, {"decision": "link", "event_id": foreign_event.pk}
        ).status_code
        == 404
    )
    assert (
        client.post(
            url, {"decision": "dismiss", "event_id": event.pk}
        ).status_code
        == 400
    )
    response = client.post(url, {"decision": "link", "event_id": event.pk})
    assert response.status_code == 200
    assert response.data["data"] == {
        "id": candidate.pk,
        "status": "resolved",
        "resolved_event_id": event.pk,
    }
    assert client.post(url, {"decision": "dismiss"}).status_code == 409
    evidence = EventEvidence.objects.get(
        event=event, message_id=candidate.message_id
    )
    assert evidence.created_by == owner
    old_activity = event.last_activity_at
    event.refresh_from_db()
    assert event.status == Event.Status.DONE
    assert event.content == "已核对"
    assert event.last_activity_at == old_activity
    assert Event.objects.filter(space=space).count() == 1
    log = SpaceAuditLog.objects.get(
        space=space,
        action="chat.deferred_event_candidate_reviewed",
        resource_id=str(candidate.pk),
    )
    assert log.metadata == {"decision": "link", "event_id": event.pk}


def test_dismiss_never_creates_event_or_deletes_source(world):
    _, _, space, _, conversation, client = world
    candidate = make_candidate(space, conversation)
    recent = make_candidate(space, conversation, 3, age=1)
    assert (
        client.post(
            review_url(space, recent), {"decision": "dismiss"}
        ).status_code
        == 404
    )
    response = client.post(
        review_url(space, candidate), {"decision": "dismiss"}
    )
    assert response.status_code == 200
    candidate.refresh_from_db()
    assert candidate.status == DeferredEventCandidate.Status.DISMISSED
    assert candidate.resolved_event_id is None
    assert Message.objects.filter(pk=candidate.message_id).exists()
    assert not Event.objects.filter(space=space).exists()
    queue = client.get(
        reverse("chat-deferred-event-candidate-list", args=[space.pk])
    )
    assert queue.data["data"]["list"] == []


def test_candidate_id_is_scoped_even_when_both_spaces_are_readable(world):
    owner, _, space, _, conversation, client = world
    other_space = make_space(owner, "deferred-second-readable")
    candidate = make_candidate(space, conversation)
    assert (
        client.post(
            review_url(other_space, candidate),
            {"decision": "dismiss"},
        ).status_code
        == 404
    )
    candidate.refresh_from_db()
    assert candidate.status == DeferredEventCandidate.Status.PENDING

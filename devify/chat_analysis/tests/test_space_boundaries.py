"""Endpoint-level space boundary matrix for chat analysis resources.

The service layer already has its own permission tests; these exercise the
HTTP surface for the actors that matter most: another space's owner, a removed
member, and a global admin without an active takeover. Every one of them must
see the same 404 as a stranger, so an ID guess cannot confirm existence.
"""

import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from chat_analysis.models import Event, Note
from chat_domain.models import Conversation, Message
from spaces.models import Space, SpaceMembership, SpaceTakeover

pytestmark = [pytest.mark.django_db, pytest.mark.integration]


def make_space(owner, slug):
    space = Space.objects.create(
        name=slug, slug=slug, kind=Space.Kind.TEAM, owner=owner
    )
    SpaceMembership.objects.create(
        space=space, user=owner, role=SpaceMembership.Role.OWNER
    )
    return space


def client_for(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def world():
    owner = User.objects.create_user(username="boundary-owner")
    space = make_space(owner, "boundary-space")
    client = client_for(owner)

    note = Note.objects.create(
        space=space,
        created_by=owner,
        note_key="boundary-note",
        title="Boundary note",
        content="Boundary content",
    )
    event = Event.objects.create(
        space=space,
        created_by=owner,
        event_key="boundary-event",
        title="Boundary event",
        content="Boundary content",
        status=Event.Status.OPEN,
    )
    tag = client.post(
        f"/api/v1/spaces/{space.pk}/tags", {"label": "风险"}, format="json"
    ).data["data"]
    question = client.post(
        f"/api/v1/spaces/{space.pk}/questions",
        {"question": "边界问题"},
        format="json",
    ).data["data"]
    topic = client.post(
        f"/api/v1/spaces/{space.pk}/topics",
        {"title": "边界主题", "instruction": "总结"},
        format="json",
    ).data["data"]
    first = client.post(
        f"/api/v1/spaces/{space.pk}/events",
        {"event_key": "boundary-relation-a", "title": "A", "content": "A"},
        format="json",
    ).data["data"]
    second = client.post(
        f"/api/v1/spaces/{space.pk}/events",
        {"event_key": "boundary-relation-b", "title": "B", "content": "B"},
        format="json",
    ).data["data"]
    relation = client.post(
        f"/api/v1/spaces/{space.pk}/event-relations",
        {
            "left_event_id": first["id"],
            "right_event_id": second["id"],
            "relation_kind": "related",
        },
        format="json",
    ).data["data"]
    conversation = Conversation.objects.create(
        space=space,
        platform=Conversation.Platform.WECHAT,
        source_namespace="boundary",
        source_conversation_id="boundary-group",
        identity_key=f"wechat:boundary:{space.pk}",
        title="Boundary group",
    )
    message = Message.objects.create(
        conversation=conversation,
        message_key="boundary-message",
        ingest_seq=1,
        sender_name="Alice",
    )

    return {
        "owner": owner,
        "space": space,
        "note": note,
        "event": event,
        "tag": tag,
        "question": question,
        "topic": topic,
        "relation": relation,
        "conversation": conversation,
        "message": message,
    }


def detail_urls(world):
    """``(method, url)`` pairs covering every read surface of one space."""

    space_id = world["space"].pk
    return {
        "note": ("get", f"/api/v1/notes/{world['note'].pk}"),
        "note_evidence": (
            "post",
            f"/api/v1/notes/{world['note'].pk}/evidence",
        ),
        "event": ("get", f"/api/v1/events/{world['event'].pk}"),
        "event_notes": ("get", f"/api/v1/events/{world['event'].pk}/notes"),
        "tag": ("get", f"/api/v1/tags/{world['tag']['id']}"),
        "question": (
            "get",
            f"/api/v1/spaces/{space_id}/questions/{world['question']['id']}",
        ),
        "topic": ("get", f"/api/v1/topics/{world['topic']['id']}"),
        "relation": (
            "get",
            f"/api/v1/event-relations/{world['relation']['id']}",
        ),
        "space_notes": ("get", f"/api/v1/spaces/{space_id}/notes"),
        "space_events": ("get", f"/api/v1/spaces/{space_id}/events"),
        "space_tags": ("get", f"/api/v1/spaces/{space_id}/tags"),
        "space_topics": ("get", f"/api/v1/spaces/{space_id}/topics"),
        "space_questions": ("get", f"/api/v1/spaces/{space_id}/questions"),
        "conversation": (
            "get",
            f"/api/v1/spaces/{space_id}/conversations/"
            f"{world['conversation'].pk}",
        ),
        "space_conversations": (
            "get",
            f"/api/v1/spaces/{space_id}/conversations",
        ),
        "message_list": (
            "get",
            f"/api/v1/spaces/{space_id}/conversations/"
            f"{world['conversation'].pk}/messages",
        ),
        "message": (
            "get",
            f"/api/v1/spaces/{space_id}/conversations/"
            f"{world['conversation'].pk}/messages/{world['message'].pk}",
        ),
    }


def assert_no_access(client, world):
    for name, (method, url) in detail_urls(world).items():
        response = getattr(client, method)(url, {}, format="json")
        assert response.status_code == 404, (name, response.status_code)


def outsiders():
    """Actors that must never read space A's chat analysis data."""

    other_owner = User.objects.create_user(username="boundary-other-owner")
    make_space(other_owner, "boundary-other-space")
    removed = User.objects.create_user(username="boundary-removed")
    staff = User.objects.create_user(username="boundary-staff", is_staff=True)
    return other_owner, removed, staff


def test_another_space_owner_gets_404_on_every_resource(world):
    other_owner, _, _ = outsiders()
    assert_no_access(client_for(other_owner), world)


def test_removed_member_gets_404_on_every_resource(world):
    other_owner, removed, _ = outsiders()
    SpaceMembership.objects.create(
        space=world["space"],
        user=removed,
        role=SpaceMembership.Role.USER,
        status=SpaceMembership.Status.REMOVED,
    )
    assert_no_access(client_for(removed), world)


def test_global_staff_without_takeover_gets_404(world):
    _, _, staff = outsiders()
    assert_no_access(client_for(staff), world)


def test_ended_takeover_no_longer_grants_access(world):
    _, _, staff = outsiders()
    takeover = SpaceTakeover.objects.create(
        space=world["space"], admin=staff, reason="incident review"
    )
    takeover.active = False
    takeover.save(update_fields=("active",))

    client = client_for(staff)
    assert client.get(f"/api/v1/notes/{world['note'].pk}").status_code == 404


def test_active_takeover_grants_read_access(world):
    _, _, staff = outsiders()
    SpaceTakeover.objects.create(
        space=world["space"], admin=staff, reason="incident review"
    )
    client = client_for(staff)

    assert client.get(f"/api/v1/notes/{world['note'].pk}").status_code == 200
    assert client.get(f"/api/v1/events/{world['event'].pk}").status_code == 200


def test_other_space_owner_cannot_write(world):
    other_owner, _, _ = outsiders()
    client = client_for(other_owner)
    space_id = world["space"].pk

    writes = [
        (
            "note",
            client.post(
                f"/api/v1/spaces/{space_id}/notes",
                {"note_key": "injected", "title": "x", "content": "y"},
                format="json",
            ),
        ),
        (
            "event",
            client.post(
                f"/api/v1/spaces/{space_id}/events",
                {"event_key": "injected", "title": "x", "content": "y"},
                format="json",
            ),
        ),
        (
            "tag",
            client.post(
                f"/api/v1/spaces/{space_id}/tags",
                {"label": "injected"},
                format="json",
            ),
        ),
        (
            "note delete",
            client.delete(f"/api/v1/notes/{world['note'].pk}"),
        ),
        (
            "event delete",
            client.delete(f"/api/v1/events/{world['event'].pk}"),
        ),
    ]

    for name, response in writes:
        assert response.status_code == 404, (name, response.status_code)

    assert Note.objects.filter(space=world["space"]).count() == 1
    assert Event.objects.filter(space=world["space"]).count() == 3


def test_archived_space_stays_readable_but_rejects_writes(world):
    space = world["space"]
    space.status = Space.Status.ARCHIVED
    space.save(update_fields=("status", "updated_at"))
    client = client_for(world["owner"])

    assert client.get(f"/api/v1/notes/{world['note'].pk}").status_code == 200
    created = client.post(
        f"/api/v1/spaces/{space.pk}/notes",
        {"note_key": "archived-note", "title": "x", "content": "y"},
        format="json",
    )
    assert created.status_code in (404, 403, 409)
    assert not Note.objects.filter(note_key="archived-note").exists()


def test_resource_copy_requires_source_read_permission(world):
    stranger = User.objects.create_user(username="copy-stranger")
    make_space(stranger, "copy-stranger-space")
    client = client_for(stranger)

    response = client.post(
        f"/api/v1/spaces/{world['space'].pk}/resource-copies",
        {
            "source_space_id": world["space"].pk,
            "resource_type": "note",
            "resource_ids": [world["note"].pk],
        },
        format="json",
    )

    assert response.status_code == 404
    assert Note.objects.filter(space=world["space"]).count() == 1


def test_resource_copy_requires_target_write_permission(world):
    guest = User.objects.create_user(username="copy-guest")
    SpaceMembership.objects.create(
        space=world["space"],
        user=guest,
        role=SpaceMembership.Role.GUEST,
    )
    target = Space.objects.create(
        name="guest-target",
        slug="guest-target",
        kind=Space.Kind.TEAM,
        owner=world["owner"],
    )
    SpaceMembership.objects.create(
        space=target, user=guest, role=SpaceMembership.Role.GUEST
    )
    client = client_for(guest)

    response = client.post(
        f"/api/v1/spaces/{target.pk}/resource-copies",
        {
            "source_space_id": world["space"].pk,
            "resource_type": "note",
            "resource_ids": [world["note"].pk],
        },
        format="json",
    )

    assert response.status_code == 403
    assert not Note.objects.filter(space=target).exists()


def test_resource_copy_ignores_ids_from_another_space(world):
    other_owner = User.objects.create_user(username="copy-other-owner")
    other_space = make_space(other_owner, "copy-other-space")
    foreign = Note.objects.create(
        space=other_space,
        created_by=other_owner,
        note_key="foreign-note",
        title="Foreign",
        content="Not yours",
    )
    client = client_for(world["owner"])

    response = client.post(
        f"/api/v1/spaces/{world['space'].pk}/resource-copies",
        {
            "source_space_id": world["space"].pk,
            "resource_type": "note",
            "resource_ids": [world["note"].pk, foreign.pk],
        },
        format="json",
    )

    assert response.status_code == 201
    copied_ids = [
        item["source_id"] for item in response.data["data"]["copied"]
    ]
    assert copied_ids == [world["note"].pk]
    assert not Note.objects.filter(
        space=world["space"], title="Foreign"
    ).exists()


def test_resource_copy_into_archived_space_is_rejected(world):
    target = Space.objects.create(
        name="archived-target",
        slug="archived-target",
        kind=Space.Kind.TEAM,
        owner=world["owner"],
        status=Space.Status.ARCHIVED,
    )
    SpaceMembership.objects.create(
        space=target, user=world["owner"], role=SpaceMembership.Role.OWNER
    )
    client = client_for(world["owner"])

    response = client.post(
        f"/api/v1/spaces/{target.pk}/resource-copies",
        {
            "source_space_id": world["space"].pk,
            "resource_type": "note",
            "resource_ids": [world["note"].pk],
        },
        format="json",
    )

    assert response.status_code == 403
    assert not Note.objects.filter(space=target).exists()


def test_copied_event_links_stay_inside_the_target_space(world):
    """A copied event must not keep a link to a source-space note."""

    from chat_analysis.models import EventNote

    source_event = Event.objects.create(
        space=world["space"],
        created_by=world["owner"],
        event_key="copy-source-event",
        title="Source event",
        content="Source content",
    )
    source_note = Note.objects.create(
        space=world["space"],
        created_by=world["owner"],
        note_key="copy-source-note",
        title="Source note",
        content="Source note content",
    )
    EventNote.objects.create(
        event=source_event, note=source_note, created_by=world["owner"]
    )
    target = Space.objects.create(
        name="copy-target",
        slug="copy-target-space",
        kind=Space.Kind.TEAM,
        owner=world["owner"],
    )
    SpaceMembership.objects.create(
        space=target, user=world["owner"], role=SpaceMembership.Role.OWNER
    )
    client = client_for(world["owner"])

    response = client.post(
        f"/api/v1/spaces/{target.pk}/resource-copies",
        {
            "source_space_id": world["space"].pk,
            "resource_type": "event",
            "resource_ids": [source_event.pk],
            "copy_notes": True,
        },
        format="json",
    )

    assert response.status_code == 201
    copied_event_id = response.data["data"]["copied"][0]["id"]
    links = EventNote.objects.filter(event_id=copied_event_id)
    assert links.exists()
    for link in links:
        assert link.note.space_id == target.pk
        assert link.event.space_id == target.pk

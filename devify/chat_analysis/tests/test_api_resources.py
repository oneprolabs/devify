import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from chat_analysis.models import Event, EventNote, EventRelation, Note
from chat_domain.models import Conversation, Message, MessagePart
from spaces.models import Space, SpaceMembership

pytestmark = [pytest.mark.django_db, pytest.mark.integration]


def make_space(owner, slug):
    space = Space.objects.create(
        name=slug,
        slug=slug,
        kind=Space.Kind.TEAM,
        owner=owner,
    )
    SpaceMembership.objects.create(
        space=space,
        user=owner,
        role=SpaceMembership.Role.OWNER,
    )
    return space


def make_message(space):
    conversation = Conversation.objects.create(
        space=space,
        platform=Conversation.Platform.WECHAT,
        source_namespace="account:local",
        source_conversation_id="group-a",
        identity_key=f"wechat:account:local:group-a-{space.pk}",
    )
    message = Message.objects.create(
        conversation=conversation,
        message_key="src:1",
        ingest_seq=1,
    )
    MessagePart.objects.create(
        message=message,
        part_key="text-1",
        kind=MessagePart.Kind.TEXT,
        text="source evidence",
    )
    return message


def test_member_can_create_note_add_evidence_and_edit_it():
    owner = User.objects.create_user(username="resource-api-owner")
    member = User.objects.create_user(username="resource-api-member")
    space = make_space(owner, "resource-api-team")
    SpaceMembership.objects.create(
        space=space,
        user=member,
        role=SpaceMembership.Role.USER,
    )
    message = make_message(space)
    client = APIClient()
    client.force_authenticate(user=member)

    created = client.post(
        f"/api/v1/spaces/{space.pk}/notes",
        {
            "note_key": "manual-1",
            "title": "Follow up",
            "content": "Customer needs a quote.",
        },
        format="json",
    )
    assert created.status_code == 201
    note_id = created.data["data"]["id"]

    evidence = client.post(
        f"/api/v1/notes/{note_id}/evidence",
        {"message_id": message.pk, "message_part_id": message.parts.get().pk},
        format="json",
    )
    assert evidence.status_code == 201

    updated = client.patch(
        f"/api/v1/notes/{note_id}",
        {"title": "Updated follow up"},
        format="json",
    )
    assert updated.status_code == 200
    assert updated.data["data"]["title"] == "Updated follow up"

    Note.objects.filter(pk=note_id).update(
        structured_data={"facts": [{"text": "Customer confirmed the scope."}]}
    )
    detail = client.get(f"/api/v1/notes/{note_id}")
    assert detail.status_code == 200
    assert detail.data["data"]["structured_data"]["facts"][0]["text"] == (
        "Customer confirmed the scope."
    )
    assert len(detail.data["data"]["evidence"]) == 1


def test_guest_can_read_but_cannot_create_note_or_event():
    owner = User.objects.create_user(username="resource-guest-owner")
    guest = User.objects.create_user(username="resource-guest")
    space = make_space(owner, "resource-guest-team")
    SpaceMembership.objects.create(
        space=space,
        user=guest,
        role=SpaceMembership.Role.GUEST,
    )
    client = APIClient()
    client.force_authenticate(user=guest)

    assert client.get(f"/api/v1/spaces/{space.pk}/notes").status_code == 200
    assert (
        client.post(
            f"/api/v1/spaces/{space.pk}/notes",
            {"note_key": "guest", "title": "Guest", "content": "No."},
            format="json",
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"/api/v1/spaces/{space.pk}/events",
            {
                "event_key": "guest-event",
                "title": "Guest",
                "content": "No.",
            },
            format="json",
        ).status_code
        == 404
    )


def test_member_can_create_event_assign_notes_and_create_relation():
    owner = User.objects.create_user(username="resource-event-owner")
    space = make_space(owner, "resource-event-team")
    client = APIClient()
    client.force_authenticate(user=owner)

    note = client.post(
        f"/api/v1/spaces/{space.pk}/notes",
        {"note_key": "event-note", "title": "Note", "content": "Text."},
        format="json",
    ).data["data"]
    event_payload = {
        "event_key": "event-1",
        "title": "Quote",
        "content": "Prepare a quote.",
        "status": Event.Status.OPEN,
    }
    event = client.post(
        f"/api/v1/spaces/{space.pk}/events",
        event_payload,
        format="json",
    ).data["data"]
    second = client.post(
        f"/api/v1/spaces/{space.pk}/events",
        {**event_payload, "event_key": "event-2", "title": "Delivery"},
        format="json",
    ).data["data"]

    assigned = client.post(
        f"/api/v1/events/{event['id']}/notes",
        {"note_ids": [note["id"]]},
        format="json",
    )
    assert assigned.status_code == 200
    assert EventNote.objects.filter(
        event_id=event["id"], note_id=note["id"]
    ).exists()

    relation = client.post(
        f"/api/v1/spaces/{space.pk}/event-relations",
        {
            "left_event_id": event["id"],
            "right_event_id": second["id"],
            "relation_kind": EventRelation.RelationKind.RELATED,
            "source_note_ids": [note["id"]],
        },
        format="json",
    )
    assert relation.status_code == 201
    assert relation.data["data"]["source_note_ids"] == [note["id"]]

    detail = client.get(f"/api/v1/events/{event['id']}")
    assert detail.status_code == 200
    assert detail.data["data"]["note_ids"] == [note["id"]]


def test_event_notes_include_message_evidence():
    owner = User.objects.create_user(username="resource-evidence-owner")
    space = make_space(owner, "resource-evidence-team")
    message = make_message(space)
    client = APIClient()
    client.force_authenticate(user=owner)

    note = client.post(
        f"/api/v1/spaces/{space.pk}/notes",
        {"note_key": "evidence-note", "title": "Note", "content": "Text."},
        format="json",
    ).data["data"]
    client.post(
        f"/api/v1/notes/{note['id']}/evidence",
        {"message_id": message.pk, "message_part_id": message.parts.get().pk},
        format="json",
    )
    event = client.post(
        f"/api/v1/spaces/{space.pk}/events",
        {
            "event_key": "evidence-event",
            "title": "Quote",
            "content": "Prepare a quote.",
        },
        format="json",
    ).data["data"]
    client.post(
        f"/api/v1/events/{event['id']}/notes",
        {"note_ids": [note["id"]]},
        format="json",
    )

    response = client.get(f"/api/v1/events/{event['id']}/notes")
    assert response.status_code == 200
    entries = response.data["data"]["list"]
    assert len(entries) == 1
    assert entries[0]["evidence"][0]["message_id"] == message.pk
    assert (
        entries[0]["evidence"][0]["conversation_id"]
        == message.conversation_id
    )


def test_cross_space_note_and_event_are_not_visible():
    owner = User.objects.create_user(username="resource-isolation-owner")
    first = make_space(owner, "resource-first")
    second = make_space(owner, "resource-second")
    client = APIClient()
    client.force_authenticate(user=owner)
    note = client.post(
        f"/api/v1/spaces/{second.pk}/notes",
        {"note_key": "foreign-note", "title": "Foreign", "content": "Text."},
        format="json",
    ).data["data"]
    event = client.post(
        f"/api/v1/spaces/{second.pk}/events",
        {
            "event_key": "foreign-event",
            "title": "Foreign",
            "content": "Text.",
        },
        format="json",
    ).data["data"]

    assert client.get(f"/api/v1/notes/{note['id']}").status_code == 200
    assert (
        client.get(f"/api/v1/spaces/{first.pk}/notes").data["data"]["list"]
        == []
    )
    assert client.get(f"/api/v1/events/{event['id']}").status_code == 200


def test_only_author_or_manager_can_edit_note():
    owner = User.objects.create_user(username="resource-edit-owner")
    member = User.objects.create_user(username="resource-edit-member")
    other = User.objects.create_user(username="resource-edit-other")
    space = make_space(owner, "resource-edit-team")
    SpaceMembership.objects.create(
        space=space, user=member, role=SpaceMembership.Role.USER
    )
    SpaceMembership.objects.create(
        space=space, user=other, role=SpaceMembership.Role.USER
    )
    client = APIClient()
    client.force_authenticate(user=member)
    note = client.post(
        f"/api/v1/spaces/{space.pk}/notes",
        {"note_key": "owned-note", "title": "Mine", "content": "Text."},
        format="json",
    ).data["data"]
    client.force_authenticate(user=other)
    assert (
        client.patch(
            f"/api/v1/notes/{note['id']}",
            {"title": "Not mine"},
            format="json",
        ).status_code
        == 403
    )
    client.force_authenticate(user=owner)
    assert (
        client.patch(
            f"/api/v1/notes/{note['id']}",
            {"title": "Manager edit"},
            format="json",
        ).status_code
        == 200
    )

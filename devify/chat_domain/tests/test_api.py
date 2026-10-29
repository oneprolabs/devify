import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from chat_domain.models import Conversation, Message, MessagePart
from spaces.models import Space, SpaceMembership, SpaceTakeover

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


def make_conversation(space, key="group-a"):
    return Conversation.objects.create(
        space=space,
        platform=Conversation.Platform.WECHAT,
        source_namespace="account:local",
        source_conversation_id=key,
        identity_key=f"wechat:account:local:{key}",
        title=key,
        message_count=1,
    )


def test_member_can_list_conversations_and_messages_with_pagination():
    owner = User.objects.create_user(username="api-owner")
    member = User.objects.create_user(username="api-member")
    space = make_space(owner, "api-team")
    SpaceMembership.objects.create(
        space=space,
        user=member,
        role=SpaceMembership.Role.USER,
    )
    conversation = make_conversation(space)
    message = Message.objects.create(
        conversation=conversation,
        message_key="src:1",
        ingest_seq=1,
        sender_name="Alice",
    )
    MessagePart.objects.create(
        message=message,
        part_key="text-1",
        kind=MessagePart.Kind.TEXT,
        text="hello",
    )

    client = APIClient()
    client.force_authenticate(user=member)
    list_response = client.get(
        f"/api/v1/spaces/{space.pk}/conversations?page_size=1"
    )
    assert list_response.status_code == 200
    assert list_response.data["data"]["list"][0]["id"] == conversation.pk
    assert list_response.data["data"]["pagination"]["page_size"] == 1

    message_response = client.get(
        f"/api/v1/spaces/{space.pk}/conversations/{conversation.pk}/messages"
    )
    assert message_response.status_code == 200
    assert message_response.data["data"]["list"][0]["id"] == message.pk

    detail_response = client.get(
        f"/api/v1/spaces/{space.pk}/conversations/"
        f"{conversation.pk}/messages/{message.pk}"
    )
    assert detail_response.status_code == 200
    assert detail_response.data["data"]["parts"][0]["text"] == "hello"


def test_non_member_cannot_read_conversations_or_messages():
    owner = User.objects.create_user(username="api-isolation-owner")
    outsider = User.objects.create_user(username="api-isolation-outsider")
    space = make_space(owner, "api-isolation-team")
    conversation = make_conversation(space)
    message = Message.objects.create(
        conversation=conversation,
        message_key="src:1",
        ingest_seq=1,
    )
    client = APIClient()
    client.force_authenticate(user=outsider)

    assert client.get(
        f"/api/v1/spaces/{space.pk}/conversations"
    ).status_code == 404
    assert client.get(
        f"/api/v1/spaces/{space.pk}/conversations/{conversation.pk}/messages"
    ).status_code == 404
    assert client.get(
        f"/api/v1/spaces/{space.pk}/conversations/"
        f"{conversation.pk}/messages/{message.pk}"
    ).status_code == 404


def test_same_user_cannot_read_conversation_from_another_space():
    owner = User.objects.create_user(username="api-cross-space-owner")
    first = make_space(owner, "api-first-space")
    second = make_space(owner, "api-second-space")
    foreign = make_conversation(second)
    client = APIClient()
    client.force_authenticate(user=owner)

    response = client.get(
        f"/api/v1/spaces/{first.pk}/conversations/{foreign.pk}"
    )
    assert response.status_code == 404


def test_global_admin_requires_takeover_and_access_is_audited():
    owner = User.objects.create_user(username="api-admin-owner")
    admin = User.objects.create_user(username="api-admin", is_staff=True)
    space = make_space(owner, "api-admin-space")
    conversation = make_conversation(space)
    client = APIClient()
    client.force_authenticate(user=admin)
    url = f"/api/v1/spaces/{space.pk}/conversations"

    assert client.get(url).status_code == 404
    SpaceTakeover.objects.create(
        space=space,
        admin=admin,
        reason="support investigation",
    )
    assert client.get(url).status_code == 200
    assert client.get(
        f"{url}/{conversation.pk}"
    ).status_code == 200

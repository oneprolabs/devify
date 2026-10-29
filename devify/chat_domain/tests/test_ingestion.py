from datetime import timedelta

import pytest
from django.contrib.auth.models import User
from django.utils import timezone

from chat_domain.models import (
    Conversation,
    Message,
    MessageOrigin,
    MessagePart,
)
from chat_domain.services import (
    build_identity_key,
    build_message_key,
    ingest_message,
    record_message_origin,
    refresh_conversation_counters,
    upsert_conversation,
    upsert_message,
    upsert_message_part,
)
from chat_ingestion.models import UploadBatch, UploadItem
from spaces.models import Space, SpaceMembership

pytestmark = [pytest.mark.django_db, pytest.mark.integration]


def make_space(user, slug):
    space = Space.objects.create(
        name=f"Space {slug}",
        slug=slug,
        kind=Space.Kind.TEAM,
        owner=user,
    )
    SpaceMembership.objects.create(
        space=space,
        user=user,
        role=SpaceMembership.Role.OWNER,
    )
    return space


def make_upload_item(space, user, key):
    batch = UploadBatch.objects.create(
        space=space,
        uploaded_by=user,
        source_type=UploadBatch.SourceType.WECHAT,
        idempotency_key=key,
    )
    return UploadItem.objects.create(batch=batch, path="messages.jsonl")


def conversation(space, title="Project group"):
    return upsert_conversation(
        space=space,
        platform=Conversation.Platform.WECHAT,
        source_namespace="account:wxid-1",
        source_conversation_id="group-a",
        title=title,
        kind=Conversation.Kind.GROUP,
    ).conversation


def test_conversation_identity_is_deduplicated_per_space():
    user = User.objects.create_user(username="chat-owner")
    space = make_space(user, "chat-space")

    first = upsert_conversation(
        space=space,
        platform=Conversation.Platform.WECHAT,
        source_namespace="account:wxid-1",
        source_conversation_id="group-a",
        title="Project group",
    )
    second = upsert_conversation(
        space=space,
        platform=Conversation.Platform.WECHAT,
        source_namespace="account:wxid-1",
        source_conversation_id="group-a",
        title="Renamed group",
        metadata={"member_count": 12},
    )

    assert first.created is True
    assert second.created is False
    assert first.conversation.pk == second.conversation.pk
    assert Conversation.objects.filter(space=space).count() == 1
    second.conversation.refresh_from_db()
    assert second.conversation.title == "Renamed group"
    assert second.conversation.metadata == {"member_count": 12}


def test_same_source_identity_in_another_space_is_not_merged():
    owner = User.objects.create_user(username="chat-owner-2")
    personal = make_space(owner, "chat-personal")
    team = make_space(owner, "chat-team")

    first = conversation(personal)
    second = conversation(team)

    assert first.pk != second.pk
    assert first.identity_key == second.identity_key


def test_identity_key_requires_a_stable_source_id_or_scope():
    with pytest.raises(ValueError):
        build_identity_key(
            platform="wechat",
            source_namespace="account:wxid-1",
        )

    scoped = build_identity_key(
        platform="wechat",
        source_namespace="account:wxid-1",
        scope_key="export-2026-10-29",
    )
    assert scoped.endswith("scope%3Aexport-2026-10-29")


def test_message_without_source_id_requires_locator_and_file_hash():
    with pytest.raises(ValueError):
        build_message_key(record_locator_key="row:1")

    key = build_message_key(
        record_locator_key="row:1",
        file_sha256="a" * 64,
    )
    assert key.startswith("loc:")


def test_repeated_source_identity_keeps_one_message_and_appends_origin():
    user = User.objects.create_user(username="chat-owner-3")
    space = make_space(user, "chat-space-3")
    target = conversation(space)
    first_item = make_upload_item(space, user, "batch-1")
    second_item = make_upload_item(space, user, "batch-2")
    occurred_at = timezone.now()

    first = ingest_message(
        conversation=target,
        source_message_id="9007199254740993",
        sender_key="wxid-sender",
        sender_name="Alice",
        direction=Message.Direction.INCOMING,
        occurred_at=occurred_at,
        parts=[
            {
                "part_key": "p1",
                "kind": MessagePart.Kind.TEXT,
                "ordinal": 0,
                "text": "hello",
            }
        ],
        origin={
            "upload_item": first_item,
            "locator_key": "messages.jsonl:1",
            "parser_version": "wechat.v1",
        },
    )
    second = ingest_message(
        conversation=target,
        source_message_id="9007199254740993",
        sender_key="wxid-sender",
        sender_name="Alice",
        direction=Message.Direction.INCOMING,
        occurred_at=occurred_at,
        parts=[
            {
                "part_key": "p1",
                "kind": MessagePart.Kind.TEXT,
                "ordinal": 0,
                "text": "hello",
            }
        ],
        origin={
            "upload_item": second_item,
            "locator_key": "messages.jsonl:1",
            "parser_version": "wechat.v1",
        },
    )

    assert first.created is True
    assert second.created is False
    assert first.message.pk == second.message.pk
    assert Message.objects.filter(conversation=target).count() == 1
    assert MessageOrigin.objects.filter(message=first.message).count() == 2
    assert MessagePart.objects.filter(message=first.message).count() == 1
    assert second.origins_created == 1

    target.refresh_from_db()
    assert target.message_count == 1
    assert target.last_message_at == occurred_at
    assert first.message.ingest_seq == 1


def test_messages_without_stable_identity_are_not_merged_by_content():
    user = User.objects.create_user(username="chat-owner-4")
    space = make_space(user, "chat-space-4")
    target = conversation(space)

    first, created_first = upsert_message(
        conversation=target,
        record_locator_key="messages.jsonl:1",
        file_sha256="b" * 64,
        source_fields={"text": "same text"},
    )
    second, created_second = upsert_message(
        conversation=target,
        record_locator_key="messages.jsonl:2",
        file_sha256="b" * 64,
        source_fields={"text": "same text"},
    )

    assert created_first is True
    assert created_second is True
    assert first.pk != second.pk


def test_reply_target_must_belong_to_the_same_conversation():
    user = User.objects.create_user(username="chat-owner-5")
    space = make_space(user, "chat-space-5")
    first = conversation(space)
    second = upsert_conversation(
        space=space,
        platform=Conversation.Platform.WECHAT,
        source_namespace="account:wxid-1",
        source_conversation_id="group-b",
        title="Other group",
    ).conversation
    parent, _ = upsert_message(
        conversation=second,
        message_key="src:parent",
    )

    with pytest.raises(ValueError):
        upsert_message(
            conversation=first,
            message_key="src:child",
            reply_to=parent,
        )


def test_message_parts_deduplicate_and_update_content():
    user = User.objects.create_user(username="chat-owner-6")
    space = make_space(user, "chat-space-6")
    target = conversation(space)
    message, _ = upsert_message(
        conversation=target,
        message_key="src:message-1",
    )

    part, created = upsert_message_part(
        message=message,
        part_key="p1",
        kind=MessagePart.Kind.TEXT,
        text="first pass",
    )
    same, created_again = upsert_message_part(
        message=message,
        part_key="p1",
        kind=MessagePart.Kind.TEXT,
        text="second pass",
    )

    assert created is True
    assert created_again is False
    assert same.pk == part.pk
    same.refresh_from_db()
    assert same.text == "second pass"
    assert MessagePart.objects.filter(message=message).count() == 1


def test_message_part_parent_must_not_create_a_cycle():
    user = User.objects.create_user(username="chat-owner-7")
    space = make_space(user, "chat-space-7")
    target = conversation(space)
    message, _ = upsert_message(
        conversation=target,
        message_key="src:message-7",
    )
    root, _ = upsert_message_part(
        message=message,
        part_key="root",
        kind=MessagePart.Kind.QUOTE,
    )
    child, _ = upsert_message_part(
        message=message,
        part_key="child",
        kind=MessagePart.Kind.TEXT,
        parent_part=root,
    )

    with pytest.raises(ValueError):
        upsert_message_part(
            message=message,
            part_key="root",
            kind=MessagePart.Kind.QUOTE,
            parent_part=child,
        )


def test_origin_cannot_cross_space_boundaries():
    owner = User.objects.create_user(username="chat-owner-8")
    first_space = make_space(owner, "chat-space-8a")
    second_space = make_space(owner, "chat-space-8b")
    target = conversation(first_space)
    message, _ = upsert_message(
        conversation=target,
        message_key="src:message-8",
    )
    foreign_item = make_upload_item(second_space, owner, "batch-8")

    with pytest.raises(ValueError):
        record_message_origin(
            message=message,
            upload_item=foreign_item,
            locator_key="messages.jsonl:1",
            parser_version="wechat.v1",
        )


def test_conversation_counters_only_include_its_messages():
    user = User.objects.create_user(username="chat-owner-9")
    space = make_space(user, "chat-space-9")
    target = conversation(space)
    earlier = timezone.now() - timedelta(hours=2)
    later = timezone.now()

    ingest_message(
        conversation=target,
        message_key="src:m1",
        occurred_at=earlier,
    )
    ingest_message(
        conversation=target,
        message_key="src:m2",
        occurred_at=later,
    )
    ingest_message(
        conversation=target,
        message_key="src:m1",
        occurred_at=earlier,
    )

    refreshed = refresh_conversation_counters(target)

    assert refreshed.message_count == 2
    assert refreshed.last_message_at == later

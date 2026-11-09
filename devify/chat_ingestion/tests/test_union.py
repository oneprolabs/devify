"""Two accounts uploading the same group converge on one conversation."""

import pytest
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from chat_analysis.models import AnalysisJob
from chat_domain.models import Conversation, Message, MessageOrigin
from chat_ingestion.models import UploadBatch
from chat_ingestion.tests.archives import (
    DEFAULT_CONVERSATIONS,
    build_archive,
    default_manifest,
)
from spaces.models import Space, SpaceMembership

pytestmark = [pytest.mark.django_db, pytest.mark.integration]


@pytest.fixture(autouse=True)
def archive_storage(settings, tmp_path):
    settings.CHAT_UPLOAD_ARCHIVE_DIR = str(tmp_path / "chat_archives")
    settings.CHAT_MEDIA_DIR = str(tmp_path / "chat_media")
    settings.CHAT_UPLOAD_PARSE_INLINE = True
    settings.CHAT_UPLOAD_ANALYSIS_INLINE = True
    settings.CHAT_ANALYSIS_LLM_ENABLED = False


def make_team(owner, slug):
    space = Space.objects.create(
        name=slug, slug=slug, kind=Space.Kind.TEAM, owner=owner
    )
    SpaceMembership.objects.create(
        space=space, user=owner, role=SpaceMembership.Role.OWNER
    )
    return space


def participant(space, username):
    user = User.objects.create_user(username=username)
    SpaceMembership.objects.create(
        space=space, user=user, role=SpaceMembership.Role.USER
    )
    return user


# The same two messages as two accounts see them: local ids differ, the
# outgoing message is only outgoing for its author, and display names are
# per contact book.
MESSAGES_A = [
    {
        "conversation_id": "group-a",
        "message_key": "src:1",
        "source_message_id": "1",
        "sender_key": "wx-a",
        "sender_name": "甲",
        "direction": "incoming",
        "occurred_at": "2026-10-20T09:00:00+08:00",
        "source_order": 1,
    },
    {
        "conversation_id": "group-a",
        "message_key": "src:2",
        "source_message_id": "2",
        "sender_key": "wx-self-a",
        "sender_name": "我",
        "direction": "outgoing",
        "occurred_at": "2026-10-20T09:05:00+08:00",
        "source_order": 2,
    },
]

MESSAGES_B = [
    {
        "conversation_id": "group-a",
        "message_key": "src:11",
        "source_message_id": "11",
        "sender_key": "wx-a",
        "sender_name": "甲(备注)",
        "direction": "incoming",
        "occurred_at": "2026-10-20T09:00:00+08:00",
        "source_order": 1,
    },
    {
        "conversation_id": "group-a",
        "message_key": "src:12",
        "source_message_id": "12",
        "sender_key": "wx-self-a",
        "sender_name": "老王",
        "direction": "incoming",
        "occurred_at": "2026-10-20T09:05:00+08:00",
        "source_order": 2,
    },
]

PARTS = [
    {
        "conversation_id": "group-a",
        "message_key": "src:1",
        "part_key": "p0",
        "kind": "text",
        "ordinal": 0,
        "text": "早上好",
    },
    {
        "conversation_id": "group-a",
        "message_key": "src:2",
        "part_key": "p0",
        "kind": "text",
        "ordinal": 0,
        "text": "今天对齐一下",
    },
]


def parts_for(key_one, key_two):
    parts = [dict(part) for part in PARTS]
    parts[0]["message_key"] = key_one
    parts[1]["message_key"] = key_two
    return parts


def archive_for(namespace, messages, key_one, key_two):
    return build_archive(
        manifest=default_manifest(
            1,
            2,
            source_namespace=namespace,
            whitelist_snapshot=["group-a"],
        ),
        conversations=DEFAULT_CONVERSATIONS,
        messages=messages,
        parts=parts_for(key_one, key_two),
        media={},
    )


def upload(user, space, key, content):
    client = APIClient()
    client.force_authenticate(user=user)
    created = client.post(
        f"/api/v1/spaces/{space.pk}/chat/uploads",
        {"source_type": "wechat", "idempotency_key": key},
        format="json",
    )
    assert created.status_code == 201
    batch = UploadBatch.objects.get(pk=created.data["data"]["id"])
    uploaded = client.put(
        f"/api/v1/chat/uploads/{batch.pk}/archive",
        {
            "archive": SimpleUploadedFile(
                "package.zip", content, content_type="application/zip"
            )
        },
        format="multipart",
    )
    assert uploaded.status_code == 200
    completed = client.post(f"/api/v1/chat/uploads/{batch.pk}/complete")
    assert completed.status_code == 200
    batch.refresh_from_db()
    return batch


def test_two_accounts_uploading_one_group_share_conversation_and_messages():
    owner = User.objects.create_user(username="union-owner")
    space = make_team(owner, "union-team")
    mate = participant(space, "union-mate")

    first = upload(
        owner,
        space,
        "union-a",
        archive_for("account:wxid-a", MESSAGES_A, "src:1", "src:2"),
    )
    second = upload(
        mate,
        space,
        "union-b",
        archive_for("account:wxid-b", MESSAGES_B, "src:11", "src:12"),
    )

    # One conversation, one copy of each message, two origins per message.
    assert Conversation.objects.filter(space=space).count() == 1
    assert Message.objects.filter(conversation__space=space).count() == 2
    assert MessageOrigin.objects.filter(
        message__conversation__space=space
    ).count() == 4
    assert AnalysisJob.objects.filter(space=space).count() == 1

    # The second upload introduced nothing new and reports the hit.
    assert first.message_count == 2
    assert first.duplicate_count == 0
    assert second.message_count == 0
    assert second.duplicate_count == 2

    conversation = Conversation.objects.get(space=space)
    namespaces = conversation.metadata.get("source_namespaces") or []
    assert "account:wxid-a" in namespaces
    assert "account:wxid-b" in namespaces


def test_alias_resolves_the_second_account_on_a_later_upload():
    owner = User.objects.create_user(username="alias-owner")
    space = make_team(owner, "alias-team")
    mate = participant(space, "alias-mate")

    upload(
        owner,
        space,
        "alias-a",
        archive_for("account:wxid-a", MESSAGES_A, "src:1", "src:2"),
    )
    upload(
        mate,
        space,
        "alias-b",
        archive_for("account:wxid-b", MESSAGES_B, "src:11", "src:12"),
    )
    # B uploads the same records again: the alias table must find both
    # messages without creating a third copy.
    third = upload(
        mate,
        space,
        "alias-b-again",
        archive_for("account:wxid-b", MESSAGES_B, "src:11", "src:12"),
    )

    assert Message.objects.filter(conversation__space=space).count() == 2
    assert MessageOrigin.objects.filter(
        message__conversation__space=space
    ).count() == 6
    assert third.message_count == 0
    assert third.duplicate_count == 2


def test_messages_without_content_are_never_merged_by_fingerprint():
    owner = User.objects.create_user(username="empty-owner")
    space = make_team(owner, "empty-team")
    mate = participant(space, "empty-mate")

    def archive(namespace, key):
        return build_archive(
            manifest=default_manifest(
                1,
                1,
                source_namespace=namespace,
                whitelist_snapshot=["group-a"],
            ),
            conversations=DEFAULT_CONVERSATIONS,
            messages=[
                {
                    "conversation_id": "group-a",
                    "message_key": key,
                    "sender_key": "wx-system",
                    "occurred_at": "2026-10-20T09:00:00+08:00",
                    "record_kind": "system",
                }
            ],
            parts=[],
            media={},
        )

    upload(owner, space, "empty-a", archive("account:wxid-a", "src:1"))
    upload(mate, space, "empty-b", archive("account:wxid-b", "src:11"))

    # No visible content and no media: the two records stay separate.
    assert Message.objects.filter(conversation__space=space).count() == 2


def test_undated_messages_are_never_merged_by_fingerprint():
    owner = User.objects.create_user(username="undated-owner")
    space = make_team(owner, "undated-team")
    mate = participant(space, "undated-mate")

    messages_a = [
        {**MESSAGES_A[0], "occurred_at": None, "message_key": "src:1"}
    ]
    messages_b = [
        {**MESSAGES_B[0], "occurred_at": None, "message_key": "src:11"}
    ]
    parts_a = [dict(parts_for("src:1", "src:1")[0])]
    parts_b = [dict(parts_for("src:11", "src:11")[0])]

    def archive(namespace, messages, parts):
        return build_archive(
            manifest=default_manifest(
                1,
                1,
                source_namespace=namespace,
                whitelist_snapshot=["group-a"],
            ),
            conversations=DEFAULT_CONVERSATIONS,
            messages=messages,
            parts=parts,
            media={},
        )

    upload(
        owner,
        space,
        "undated-a",
        archive("account:wxid-a", messages_a, parts_a),
    )
    upload(
        mate,
        space,
        "undated-b",
        archive("account:wxid-b", messages_b, parts_b),
    )

    assert Message.objects.filter(conversation__space=space).count() == 2

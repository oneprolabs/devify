import pytest
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from chat_domain.models import (
    Conversation,
    Message,
    MessageOrigin,
    MessagePart,
)
from chat_ingestion.models import UploadBatch, UploadItem
from chat_ingestion.tests.archives import build_archive, default_manifest
from spaces.models import Space, SpaceMembership

pytestmark = [pytest.mark.django_db, pytest.mark.integration]


@pytest.fixture(autouse=True)
def archive_storage(settings, tmp_path):
    settings.CHAT_UPLOAD_ARCHIVE_DIR = str(tmp_path / "chat_archives")


def make_team(owner, slug="parse-team"):
    space = Space.objects.create(
        name="Parse Team",
        slug=slug,
        kind=Space.Kind.TEAM,
        owner=owner,
    )
    SpaceMembership.objects.create(
        space=space, user=owner, role=SpaceMembership.Role.OWNER
    )
    return space


def auth_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def start_upload(client, space, key, content):
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
    return batch


def complete(client, batch):
    return client.post(f"/api/v1/chat/uploads/{batch.pk}/complete")


def test_complete_parses_archive_into_conversations_messages_and_parts():
    owner = User.objects.create_user(username="parse-owner")
    space = make_team(owner)
    client = auth_client(owner)
    batch = start_upload(client, space, "parse-batch", build_archive())

    response = complete(client, batch)

    assert response.status_code == 200
    data = response.data["data"]
    assert data["status"] == UploadBatch.Status.COMPLETED
    assert data["message_count"] == 2
    assert data["duplicate_count"] == 0
    assert {item["path"] for item in data["items"]} >= {
        "manifest.json",
        "conversations.jsonl",
        "messages.jsonl",
        "message_parts.jsonl",
        "media/photo.png",
    }

    conversation = Conversation.objects.get(space=space)
    assert conversation.platform == Conversation.Platform.WECHAT
    assert conversation.source_namespace == "account:local-account-1"
    assert conversation.source_conversation_id == "group-a"
    assert conversation.title == "项目群"
    assert conversation.kind == Conversation.Kind.GROUP
    assert conversation.message_count == 2
    assert Message.objects.filter(conversation=conversation).count() == 2

    text_part = MessagePart.objects.get(
        message__message_key="srv:1", part_key="p0"
    )
    assert text_part.kind == MessagePart.Kind.TEXT
    assert text_part.text == "早上好"
    image_part = MessagePart.objects.get(
        message__message_key="srv:2", part_key="p0"
    )
    assert image_part.kind == MessagePart.Kind.IMAGE
    assert image_part.upload_item.path == "media/photo.png"
    assert image_part.binding_state == MessagePart.BindingState.AVAILABLE

    origins = MessageOrigin.objects.filter(
        message__conversation=conversation
    )
    assert origins.count() == 2
    assert {origin.parser_version for origin in origins} == {"wechat.v1"}


def test_reimport_dedupes_messages_and_records_new_origins():
    owner = User.objects.create_user(username="parse-reimport-owner")
    space = make_team(owner, slug="parse-reimport-team")
    client = auth_client(owner)
    content = build_archive()

    first = start_upload(client, space, "parse-first", content)
    assert complete(client, first).status_code == 200
    second = start_upload(client, space, "parse-second", content)
    response = complete(client, second)

    assert response.status_code == 200
    second.refresh_from_db()
    assert second.message_count == 0
    assert second.duplicate_count == 2
    assert Conversation.objects.count() == 1
    assert Message.objects.count() == 2
    # Both batches contribute an origin for each message; messages stay 2.
    assert MessageOrigin.objects.count() == 4
    item = UploadItem.objects.get(batch=second, path="messages.jsonl")
    assert item.status == UploadItem.Status.DUPLICATE


def test_complete_resumes_a_stuck_processing_batch():
    owner = User.objects.create_user(username="parse-resume-owner")
    space = make_team(owner, slug="parse-resume-team")
    client = auth_client(owner)
    batch = start_upload(client, space, "parse-resume", build_archive())
    batch.status = UploadBatch.Status.PROCESSING
    batch.save(update_fields=("status", "updated_at"))

    response = complete(client, batch)

    assert response.status_code == 200
    assert response.data["data"]["status"] == UploadBatch.Status.COMPLETED
    assert Message.objects.count() == 2


def test_manifest_count_mismatch_fails_the_whole_batch():
    owner = User.objects.create_user(username="parse-count-owner")
    space = make_team(owner, slug="parse-count-team")
    client = auth_client(owner)
    manifest = default_manifest(1, 3)
    batch = start_upload(
        client,
        space,
        "parse-count",
        build_archive(manifest=manifest),
    )

    response = complete(client, batch)

    assert response.status_code == 422
    assert "manifest counts 3 messages" in response.data["detail"]
    batch.refresh_from_db()
    assert batch.status == UploadBatch.Status.FAILED
    assert batch.error_message
    assert Conversation.objects.count() == 0
    assert Message.objects.count() == 0
    assert UploadItem.objects.filter(batch=batch).count() == 0


def test_unsafe_archive_path_is_rejected():
    owner = User.objects.create_user(username="parse-path-owner")
    space = make_team(owner, slug="parse-path-team")
    client = auth_client(owner)
    batch = start_upload(
        client,
        space,
        "parse-path",
        build_archive(media={"../escape.txt": b"nope"}),
    )

    response = complete(client, batch)

    assert response.status_code == 422
    assert "Unsafe archive member path" in response.data["detail"]
    assert UploadBatch.objects.get(pk=batch.pk).status == (
        UploadBatch.Status.FAILED
    )
    assert Conversation.objects.count() == 0


def test_conversation_outside_declared_scope_is_rejected():
    owner = User.objects.create_user(username="parse-scope-owner")
    space = make_team(owner, slug="parse-scope-team")
    client = auth_client(owner)
    manifest = default_manifest(1, 2)
    manifest["scope"] = {"conversation_ids": ["group-b"]}
    batch = start_upload(
        client,
        space,
        "parse-scope",
        build_archive(manifest=manifest),
    )

    response = complete(client, batch)

    assert response.status_code == 422
    assert "outside the declared scope" in response.data["detail"]


def test_manifest_platform_must_match_batch():
    owner = User.objects.create_user(username="parse-platform-owner")
    space = make_team(owner, slug="parse-platform-team")
    client = auth_client(owner)
    manifest = default_manifest(
        1, 2, schema_version="line.v1", platform="line"
    )
    batch = start_upload(
        client,
        space,
        "parse-platform",
        build_archive(manifest=manifest),
    )

    response = complete(client, batch)

    assert response.status_code == 422
    assert "does not match the upload batch" in response.data["detail"]


def test_part_cannot_reference_an_unknown_message():
    owner = User.objects.create_user(username="parse-part-owner")
    space = make_team(owner, slug="parse-part-team")
    client = auth_client(owner)
    parts = [
        {
            "conversation_id": "group-a",
            "message_key": "srv:missing",
            "part_key": "p0",
            "kind": "text",
            "text": "orphan",
        }
    ]
    batch = start_upload(
        client,
        space,
        "parse-part",
        build_archive(parts=parts),
    )

    response = complete(client, batch)

    assert response.status_code == 422
    assert "unknown message" in response.data["detail"]


def test_missing_media_is_kept_as_an_explicit_gap():
    owner = User.objects.create_user(username="parse-media-owner")
    space = make_team(owner, slug="parse-media-team")
    client = auth_client(owner)
    batch = start_upload(
        client,
        space,
        "parse-media",
        build_archive(media={}),
    )

    response = complete(client, batch)

    assert response.status_code == 200
    image_part = MessagePart.objects.get(
        message__message_key="srv:2", part_key="p0"
    )
    assert image_part.upload_item is None
    assert image_part.binding_state == MessagePart.BindingState.MISSING


def test_manifest_cannot_choose_space_or_uploader():
    owner = User.objects.create_user(username="parse-space-owner")
    other = User.objects.create_user(username="parse-space-other")
    space = make_team(owner, slug="parse-space-team")
    other_space = make_team(other, slug="parse-space-other-team")
    client = auth_client(owner)
    manifest = default_manifest(
        1,
        2,
        space_id=other_space.pk,
        uploaded_by_id=other.pk,
    )
    batch = start_upload(
        client,
        space,
        "parse-space",
        build_archive(manifest=manifest),
    )

    response = complete(client, batch)

    assert response.status_code == 200
    conversation = Conversation.objects.get()
    assert conversation.space_id == space.pk
    batch.refresh_from_db()
    assert batch.space_id == space.pk
    assert batch.uploaded_by_id == owner.pk
    assert not Conversation.objects.filter(space=other_space).exists()


def test_failed_import_can_be_retried_with_a_corrected_archive():
    owner = User.objects.create_user(username="parse-retry-owner")
    space = make_team(owner, slug="parse-retry-team")
    client = auth_client(owner)
    batch = start_upload(
        client,
        space,
        "parse-retry",
        build_archive(manifest=default_manifest(1, 3)),
    )

    failed = complete(client, batch)
    assert failed.status_code == 422

    corrected = client.put(
        f"/api/v1/chat/uploads/{batch.pk}/archive",
        {
            "archive": SimpleUploadedFile(
                "package.zip", build_archive(), content_type="application/zip"
            )
        },
        format="multipart",
    )
    assert corrected.status_code == 200

    retried = complete(client, batch)

    assert retried.status_code == 200
    batch.refresh_from_db()
    assert batch.status == UploadBatch.Status.COMPLETED
    assert batch.error_message == ""
    assert batch.message_count == 2
    assert Message.objects.count() == 2


def test_origin_file_records_a_second_source_for_the_same_message():
    owner = User.objects.create_user(username="parse-origin-owner")
    space = make_team(owner, slug="parse-origin-team")
    client = auth_client(owner)
    origins = [
        {
            "conversation_id": "group-a",
            "message_key": "srv:1",
            "locator_key": "offset:42",
            "parser_version": "wechat.v1",
            "upload_item_path": "raw/export.json",
            "record_locator": {"offset": 42},
        }
    ]
    batch = start_upload(
        client,
        space,
        "parse-origin",
        build_archive(
            origins=origins,
            extra={"raw/export.json": b"{}"},
            media={},
        ),
    )

    response = complete(client, batch)

    assert response.status_code == 200
    origin = MessageOrigin.objects.get(locator_key="offset:42")
    assert origin.upload_item.path == "raw/export.json"
    assert origin.record_locator == {"offset": 42}
    assert MessageOrigin.objects.filter(
        message__message_key="srv:1"
    ).count() == 2


def test_messages_without_ids_dedupe_by_locator_and_file_hash():
    owner = User.objects.create_user(username="parse-no-id-owner")
    space = make_team(owner, slug="parse-no-id-team")
    client = auth_client(owner)
    messages = [
        {
            "conversation_id": "group-a",
            "sender_key": "wx-a",
            "occurred_at": "2026-10-20T09:00:00+08:00",
        },
        {
            "conversation_id": "group-a",
            "sender_key": "wx-self",
            "occurred_at": "2026-10-20T09:05:00+08:00",
        },
    ]
    content = build_archive(messages=messages, parts=[], media={})

    first = start_upload(client, space, "parse-no-id-1", content)
    assert complete(client, first).status_code == 200
    second = start_upload(client, space, "parse-no-id-2", content)
    response = complete(client, second)

    assert response.status_code == 200
    keys = set(Message.objects.values_list("message_key", flat=True))
    assert len(keys) == 2
    assert all(key.startswith("loc:") for key in keys)
    second.refresh_from_db()
    assert second.message_count == 0
    assert second.duplicate_count == 2

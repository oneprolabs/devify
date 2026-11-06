"""Content-addressed media storage and its read endpoint."""

import pytest
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from chat_domain.media import media_path
from chat_domain.models import MessagePart
from chat_ingestion.models import UploadBatch
from chat_ingestion.tests.archives import DEFAULT_MEDIA, build_archive
from spaces.models import Space, SpaceMembership

pytestmark = [pytest.mark.django_db, pytest.mark.integration]

PHOTO = "media/photo.png"


@pytest.fixture(autouse=True)
def chat_storage(settings, tmp_path):
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


def upload(user, space, key="media-batch"):
    client = APIClient()
    client.force_authenticate(user=user)
    content = build_archive()
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
    return client, batch


def test_parse_stores_media_once_and_serves_it_by_digest():
    owner = User.objects.create_user(username="media-owner")
    space = make_team(owner, "media-team")

    client, batch = upload(owner, space)

    assert batch.status == UploadBatch.Status.COMPLETED
    part = MessagePart.objects.get(kind=MessagePart.Kind.IMAGE)
    assert part.media_sha256
    assert part.media_content_type == "image/png"
    stored = media_path(part.media_sha256)
    assert stored.is_file()
    assert stored.read_bytes() == DEFAULT_MEDIA[PHOTO]

    # The message API returns the digest address, not the archive address.
    messages = client.get(
        f"/api/v1/spaces/{space.pk}/conversations"
        f"/{part.message.conversation_id}/messages"
    )
    assert messages.status_code == 200
    media = next(
        item["media"]
        for item in messages.data["data"]["list"]
        if item["media"]
    )
    assert media[0]["media_url"].endswith(f"/chat-media/{part.media_sha256}")

    served = client.get(f"/api{media[0]['media_url']}")
    assert served.status_code == 200
    assert b"".join(served.streaming_content) == DEFAULT_MEDIA[PHOTO]
    assert served["Content-Type"] == "image/png"


def test_digest_media_is_hidden_from_another_space():
    owner = User.objects.create_user(username="media-owner-2")
    outsider = User.objects.create_user(username="media-outsider-2")
    space = make_team(owner, "media-team-2")
    other_space = make_team(outsider, "media-team-3")

    _client, _batch = upload(owner, space)
    part = MessagePart.objects.get(kind=MessagePart.Kind.IMAGE)
    assert part.media_sha256

    outsider_client = APIClient()
    outsider_client.force_authenticate(user=outsider)
    response = outsider_client.get(
        f"/api/v1/spaces/{other_space.pk}/chat-media/{part.media_sha256}"
    )
    assert response.status_code == 404


def test_unknown_digest_is_not_served():
    owner = User.objects.create_user(username="media-owner-3")
    space = make_team(owner, "media-team-4")
    client = APIClient()
    client.force_authenticate(user=owner)

    response = client.get(f"/api/v1/spaces/{space.pk}/chat-media/{'0' * 64}")
    assert response.status_code == 404
    bad_digest = client.get(
        f"/api/v1/spaces/{space.pk}/chat-media/not-a-digest"
    )
    assert bad_digest.status_code == 404

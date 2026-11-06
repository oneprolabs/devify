"""Withdrawing one upload keeps every other uploader's records intact."""

import pytest
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from rest_framework.test import APIClient

from chat_domain.media import media_path
from chat_domain.models import (
    Conversation,
    Message,
    MessageOrigin,
    MessagePart,
)
from chat_ingestion.models import UploadBatch
from chat_ingestion.tests.archives import (
    DEFAULT_CONVERSATIONS,
    DEFAULT_MESSAGES,
    DEFAULT_PARTS,
    build_archive,
    default_manifest,
)
from spaces.models import Space, SpaceMembership

pytestmark = [pytest.mark.django_db, pytest.mark.integration]


@pytest.fixture(autouse=True)
def storage(settings, tmp_path):
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


def participant(space, username, role=SpaceMembership.Role.USER):
    user = User.objects.create_user(username=username)
    SpaceMembership.objects.create(space=space, user=user, role=role)
    return user


def auth(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def upload(user, space, key, content):
    client = auth(user)
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


def revoke(user, batch):
    return auth(user).delete(f"/api/v1/chat/uploads/{batch.pk}")


def archive(namespace):
    return build_archive(
        manifest=default_manifest(
            1,
            2,
            source_namespace=namespace,
            whitelist_snapshot=["group-a"],
        ),
        conversations=DEFAULT_CONVERSATIONS,
        messages=DEFAULT_MESSAGES,
        parts=DEFAULT_PARTS,
        media={"media/photo.png": b"\x89PNG\r\n\x1a\nphoto"},
    )


def test_uploader_revoke_keeps_the_other_uploaders_origin_and_media():
    owner = User.objects.create_user(username="revoke-owner")
    space = make_team(owner, "revoke-team")
    mate = participant(space, "revoke-mate")

    first = upload(owner, space, "revoke-a", archive("account:wxid-a"))
    upload(mate, space, "revoke-b", archive("account:wxid-b"))
    assert Message.objects.count() == 2
    assert MessageOrigin.objects.count() == 4

    part = MessagePart.objects.get(kind=MessagePart.Kind.IMAGE)
    sha = part.media_sha256
    assert media_path(sha).is_file()

    response = revoke(owner, first)

    assert response.status_code == 204
    assert not UploadBatch.objects.filter(pk=first.pk).exists()
    # The messages stay: the second upload still carries an origin for both.
    assert Message.objects.count() == 2
    assert Message.objects.filter(orphaned_at__isnull=False).count() == 0
    assert MessageOrigin.objects.count() == 2
    # Media is content-addressed, so withdrawing the archive that first
    # carried it does not remove the file from the other upload's message.
    assert media_path(sha).is_file()
    served = auth(mate).get(
        f"/api/v1/spaces/{space.pk}/chat-media/{sha}"
    )
    assert served.status_code == 200


def test_member_cannot_revoke_someone_elses_upload():
    owner = User.objects.create_user(username="revoke-owner-2")
    space = make_team(owner, "revoke-team-2")
    member = participant(space, "revoke-member-2")
    outsider = User.objects.create_user(username="revoke-outsider-2")

    batch = upload(owner, space, "revoke-2", archive("account:wxid-a"))

    assert revoke(member, batch).status_code == 403
    assert revoke(outsider, batch).status_code == 404
    assert UploadBatch.objects.filter(pk=batch.pk).exists()


def test_admin_can_revoke_another_members_upload():
    owner = User.objects.create_user(username="revoke-owner-3")
    space = make_team(owner, "revoke-team-3")
    maintainer = participant(
        space, "revoke-maintainer-3", SpaceMembership.Role.MAINTAINER
    )
    member = participant(space, "revoke-member-3")

    batch = upload(member, space, "revoke-3", archive("account:wxid-a"))

    assert revoke(maintainer, batch).status_code == 204
    assert not UploadBatch.objects.filter(pk=batch.pk).exists()


def test_last_origin_orphans_the_message_and_purge_removes_it():
    owner = User.objects.create_user(username="revoke-owner-4")
    space = make_team(owner, "revoke-team-4")

    batch = upload(owner, space, "revoke-4", archive("account:wxid-a"))
    assert revoke(owner, batch).status_code == 204

    assert Message.objects.count() == 2
    assert Message.objects.filter(orphaned_at__isnull=False).count() == 2
    assert MessageOrigin.objects.count() == 0
    assert Conversation.objects.filter(space=space).count() == 1

    call_command("purge_orphaned_messages", "--days", "0", "--apply")

    assert Message.objects.count() == 0
    assert Conversation.objects.filter(space=space).count() == 1


def test_reupload_after_revoke_clears_the_orphaned_mark():
    owner = User.objects.create_user(username="revoke-owner-5")
    space = make_team(owner, "revoke-team-5")

    first = upload(owner, space, "revoke-5a", archive("account:wxid-a"))
    assert revoke(owner, first).status_code == 204
    assert Message.objects.filter(orphaned_at__isnull=False).count() == 2

    upload(owner, space, "revoke-5b", archive("account:wxid-a"))

    assert Message.objects.count() == 2
    assert Message.objects.filter(orphaned_at__isnull=False).count() == 0

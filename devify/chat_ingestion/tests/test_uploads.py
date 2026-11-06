import hashlib
from unittest.mock import patch

import pytest
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from chat_ingestion.models import UploadBatch
from chat_ingestion.services import (
    UploadTransitionError,
    transition_batch,
)
from chat_ingestion.tests.archives import build_archive
from spaces.models import (
    Space,
    SpaceAuditLog,
    SpaceMembership,
    SpaceTakeover,
)

pytestmark = [pytest.mark.django_db, pytest.mark.integration]


@pytest.fixture(autouse=True)
def archive_storage(settings, tmp_path):
    settings.CHAT_UPLOAD_ARCHIVE_DIR = str(tmp_path / "chat_archives")


def make_team(owner, slug="upload-team"):
    space = Space.objects.create(
        name="Upload Team",
        slug=slug,
        kind=Space.Kind.TEAM,
        owner=owner,
    )
    SpaceMembership.objects.create(
        space=space, user=owner, role=SpaceMembership.Role.OWNER
    )
    return space


def payload(key="batch-1", source_type="wechat"):
    return {
        "source_type": source_type,
        "source_account_id": "local-account-1",
        "idempotency_key": key,
        "archive_sha256": "a" * 64,
        "archive_size": 123,
    }


def create_url(space):
    return f"/api/v1/spaces/{space.pk}/chat/uploads"


def batch_url(batch, action=None):
    url = f"/api/v1/chat/uploads/{batch.pk}"
    return f"{url}/{action}" if action else url


def auth_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def archive_file(content=b"wechat-package-bytes"):
    return SimpleUploadedFile(
        "package.zip", content, content_type="application/zip"
    )


def test_member_can_create_upload_and_repeat_is_idempotent():
    owner = User.objects.create_user(username="upload-owner")
    member = User.objects.create_user(username="upload-member")
    space = make_team(owner)
    SpaceMembership.objects.create(
        space=space, user=member, role=SpaceMembership.Role.USER
    )
    client = auth_client(member)

    first = client.post(create_url(space), payload(), format="json")
    second = client.post(create_url(space), payload(), format="json")

    assert first.status_code == 201
    assert second.status_code == 200
    assert first.data["data"]["id"] == second.data["data"]["id"]
    assert (
        UploadBatch.objects.filter(space=space, uploaded_by=member).count()
        == 1
    )
    # Regression: the global camel-case parser used to rewrite the declared
    # checksum key, so the batch silently stored an empty hash.
    assert UploadBatch.objects.get().archive_sha256 == "a" * 64


@pytest.mark.django_db(transaction=True)
def test_create_upload_does_not_wait_for_shared_space_lock():
    from threading import Event, Thread
    from django.db import close_old_connections, connection, transaction
    from spaces.services import get_space_quota

    if connection.vendor != "mysql":
        pytest.skip("MariaDB foreign-key locking regression")
    owner = User.objects.create_user(username="shared-lock-owner")
    space = make_team(owner, slug="shared-lock-space")
    get_space_quota(space)
    finished = Event()
    results = []

    def create():
        close_old_connections()
        try:
            results.append(
                auth_client(owner)
                .post(create_url(space), payload(), format="json")
                .status_code
            )
        finally:
            close_old_connections()
            finished.set()

    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT id FROM spaces_space WHERE id = %s LOCK IN SHARE MODE",
                [space.pk],
            )
        worker = Thread(target=create)
        worker.start()
        completed_without_waiting = finished.wait(5)
    worker.join(timeout=10)
    assert completed_without_waiting
    assert results == [201]


def test_desktop_upload_records_the_device_from_its_token():
    from rest_framework_simplejwt.tokens import AccessToken

    from accounts.models import DesktopDevice

    owner = User.objects.create_user(username="upload-device-owner")
    space = make_team(owner, slug="upload-device-team")
    device = DesktopDevice.objects.create(
        user=owner,
        device_id="mac-device-1",
        status=DesktopDevice.Status.ACTIVE,
    )
    token = AccessToken.for_user(owner)
    token["device_id"] = device.device_id
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    response = client.post(
        create_url(space), payload("device-batch"), format="json"
    )

    assert response.status_code == 201
    assert response.data["data"]["device_id"] == device.device_id


def test_upload_records_its_trigger():
    owner = User.objects.create_user(username="upload-trigger-owner")
    space = make_team(owner, slug="upload-trigger-team")
    client = auth_client(owner)

    response = client.post(
        create_url(space),
        {**payload("scheduled-batch"), "trigger": "scheduled"},
        format="json",
    )

    assert response.status_code == 201
    assert response.data["data"]["trigger"] == "scheduled"


def test_upload_registers_its_device_and_platform():
    from accounts.models import DesktopDevice

    owner = User.objects.create_user(username="upload-platform-owner")
    space = make_team(owner, slug="upload-platform-team")
    client = auth_client(owner)

    response = client.post(
        create_url(space),
        {
            **payload("platform-batch"),
            "device_id": "upload-device-1",
            "device_label": "MacBook Pro",
            "platform": "macos",
        },
        format="json",
    )

    assert response.status_code == 201
    assert response.data["data"]["device_id"] == "upload-device-1"
    assert response.data["data"]["platform"] == "macos"
    device = DesktopDevice.objects.get(user=owner, device_id="upload-device-1")
    assert device.platform == "macos"
    assert device.label == "MacBook Pro"


def test_retry_without_optional_fields_is_not_a_conflict():
    owner = User.objects.create_user(username="upload-minimal-owner")
    space = make_team(owner, slug="upload-minimal-team")
    client = auth_client(owner)
    minimal = {"source_type": "wechat", "idempotency_key": "minimal-batch"}

    first = client.post(create_url(space), minimal, format="json")
    second = client.post(create_url(space), minimal, format="json")

    assert first.status_code == 201
    assert second.status_code == 200
    assert second.data["data"]["archive_sha256"] == ""

    changed_type = client.post(
        create_url(space),
        {**minimal, "source_type": "line"},
        format="json",
    )
    assert changed_type.status_code == 409

    declared_later = client.post(
        create_url(space),
        {**minimal, "archive_sha256": "b" * 64},
        format="json",
    )
    assert declared_later.status_code == 409


def test_guest_cannot_create_upload_and_conflicting_key_is_rejected():
    owner = User.objects.create_user(username="upload-guest-owner")
    guest = User.objects.create_user(username="upload-guest")
    space = make_team(owner, slug="upload-guest-team")
    SpaceMembership.objects.create(
        space=space, user=guest, role=SpaceMembership.Role.GUEST
    )
    client = auth_client(guest)
    assert (
        client.post(create_url(space), payload(), format="json").status_code
        == 404
    )

    client = auth_client(owner)
    assert (
        client.post(create_url(space), payload(), format="json").status_code
        == 201
    )
    conflict = client.post(
        create_url(space),
        payload(source_type="line"),
        format="json",
    )
    assert conflict.status_code == 409

    size_conflict = client.post(
        create_url(space),
        {**payload(), "archive_size": 456},
        format="json",
    )
    assert size_conflict.status_code == 409


def test_upload_status_is_visible_to_members_and_admin_only_after_takeover():
    owner = User.objects.create_user(username="upload-status-owner")
    member = User.objects.create_user(username="upload-status-member")
    admin = User.objects.create_user(
        username="upload-status-admin", is_staff=True
    )
    space = make_team(owner, slug="upload-status-team")
    SpaceMembership.objects.create(
        space=space, user=member, role=SpaceMembership.Role.USER
    )
    create_client = auth_client(owner)
    response = create_client.post(
        create_url(space),
        payload("status-batch"),
        format="json",
    )
    batch = UploadBatch.objects.get(pk=response.data["data"]["id"])
    url = batch_url(batch)

    member_client = auth_client(member)
    assert member_client.get(url).status_code == 200
    outsider = User.objects.create_user(username="upload-status-outsider")
    assert auth_client(outsider).get(url).status_code == 404
    admin_client = auth_client(admin)
    assert admin_client.get(url).status_code == 404
    SpaceTakeover.objects.create(space=space, admin=admin, reason="audit")
    assert admin_client.get(url).status_code == 200
    assert SpaceAuditLog.objects.filter(
        action="chat.upload_viewed", resource_id=str(batch.pk)
    ).exists()


def test_archive_upload_records_server_checksum_and_size():
    owner = User.objects.create_user(username="upload-archive-owner")
    space = make_team(owner, slug="upload-archive-team")
    client = auth_client(owner)
    response = client.post(
        create_url(space),
        {"source_type": "wechat", "idempotency_key": "archive-batch"},
        format="json",
    )
    batch = UploadBatch.objects.get(pk=response.data["data"]["id"])
    content = b"normalized-chat-package"

    uploaded = client.put(
        batch_url(batch, "archive"),
        {"archive": archive_file(content)},
        format="multipart",
    )

    assert uploaded.status_code == 200
    batch.refresh_from_db()
    assert batch.archive_sha256 == hashlib.sha256(content).hexdigest()
    assert batch.archive_size == len(content)
    assert batch.status == UploadBatch.Status.UPLOADING
    assert SpaceAuditLog.objects.filter(
        action="chat.archive_uploaded", resource_id=str(batch.pk)
    ).exists()


def test_archive_upload_rejects_declared_checksum_and_size_mismatch():
    owner = User.objects.create_user(username="upload-mismatch-owner")
    space = make_team(owner, slug="upload-mismatch-team")
    client = auth_client(owner)
    checksum_batch = UploadBatch.objects.create(
        space=space,
        uploaded_by=owner,
        source_type=UploadBatch.SourceType.WECHAT,
        idempotency_key="mismatch-sha",
        archive_sha256="a" * 64,
        status=UploadBatch.Status.UPLOADING,
    )
    checksum = client.put(
        batch_url(checksum_batch, "archive"),
        {"archive": archive_file(b"other-bytes")},
        format="multipart",
    )
    assert checksum.status_code == 409
    checksum_batch.refresh_from_db()
    assert checksum_batch.archive_sha256 == "a" * 64

    size_batch = UploadBatch.objects.create(
        space=space,
        uploaded_by=owner,
        source_type=UploadBatch.SourceType.WECHAT,
        idempotency_key="mismatch-size",
        archive_size=3,
        status=UploadBatch.Status.UPLOADING,
    )
    size = client.put(
        batch_url(size_batch, "archive"),
        {"archive": archive_file(b"longer-than-three")},
        format="multipart",
    )
    assert size.status_code == 409
    size_batch.refresh_from_db()
    assert size_batch.archive_size == 3


def test_archive_upload_rejects_oversized_archive(settings):
    settings.CHAT_UPLOAD_MAX_ARCHIVE_BYTES = 4
    owner = User.objects.create_user(username="upload-large-owner")
    space = make_team(owner, slug="upload-large-team")
    client = auth_client(owner)
    response = client.post(
        create_url(space),
        {"source_type": "wechat", "idempotency_key": "large-batch"},
        format="json",
    )
    batch = UploadBatch.objects.get(pk=response.data["data"]["id"])

    uploaded = client.put(
        batch_url(batch, "archive"),
        {"archive": archive_file(b"too-large")},
        format="multipart",
    )

    assert uploaded.status_code == 413
    batch.refresh_from_db()
    assert batch.archive_sha256 == ""


def test_archive_upload_requires_uploader_or_space_admin():
    owner = User.objects.create_user(username="upload-rights-owner")
    member = User.objects.create_user(username="upload-rights-member")
    guest = User.objects.create_user(username="upload-rights-guest")
    outsider = User.objects.create_user(username="upload-rights-outsider")
    space = make_team(owner, slug="upload-rights-team")
    SpaceMembership.objects.create(
        space=space, user=member, role=SpaceMembership.Role.USER
    )
    SpaceMembership.objects.create(
        space=space, user=guest, role=SpaceMembership.Role.GUEST
    )
    response = auth_client(owner).post(
        create_url(space),
        {"source_type": "wechat", "idempotency_key": "rights-batch"},
        format="json",
    )
    batch = UploadBatch.objects.get(pk=response.data["data"]["id"])

    for user in (member, guest):
        denied = auth_client(user).put(
            batch_url(batch, "archive"),
            {"archive": archive_file()},
            format="multipart",
        )
        assert denied.status_code == 403

    missing = auth_client(outsider).put(
        batch_url(batch, "archive"),
        {"archive": archive_file()},
        format="multipart",
    )
    assert missing.status_code == 404

    owner_client = auth_client(owner)
    assert (
        owner_client.put(
            batch_url(batch, "archive"),
            {"archive": archive_file()},
            format="multipart",
        ).status_code
        == 200
    )


def test_archive_upload_requires_a_file():
    owner = User.objects.create_user(username="upload-empty-owner")
    space = make_team(owner, slug="upload-empty-team")
    client = auth_client(owner)
    response = client.post(
        create_url(space),
        {"source_type": "wechat", "idempotency_key": "empty-batch"},
        format="json",
    )
    batch = UploadBatch.objects.get(pk=response.data["data"]["id"])

    uploaded = client.put(batch_url(batch, "archive"), {}, format="multipart")

    assert uploaded.status_code == 400


def test_complete_parses_archive_and_marks_batch_completed():
    owner = User.objects.create_user(username="upload-complete-owner")
    space = make_team(owner, slug="upload-complete-team")
    client = auth_client(owner)
    response = client.post(
        create_url(space),
        {"source_type": "wechat", "idempotency_key": "complete-batch"},
        format="json",
    )
    batch = UploadBatch.objects.get(pk=response.data["data"]["id"])

    early = client.post(batch_url(batch, "complete"))
    assert early.status_code == 409
    assert UploadBatch.objects.get(pk=batch.pk).status == (
        UploadBatch.Status.UPLOADING
    )

    client.put(
        batch_url(batch, "archive"),
        {"archive": archive_file(build_archive())},
        format="multipart",
    )
    completed = client.post(batch_url(batch, "complete"))
    repeated = client.post(batch_url(batch, "complete"))

    assert completed.status_code == 200
    assert completed.data["data"]["status"] == UploadBatch.Status.COMPLETED
    assert completed.data["data"]["message_count"] == 2
    assert repeated.status_code == 200
    assert repeated.data["data"]["status"] == UploadBatch.Status.COMPLETED
    assert (
        SpaceAuditLog.objects.filter(
            action="chat.upload_completed", resource_id=str(batch.pk)
        ).count()
        == 1
    )


def test_complete_enqueues_parser_when_async_mode_is_enabled(settings):
    owner = User.objects.create_user(username="upload-async-owner")
    space = make_team(owner, slug="upload-async-team")
    client = auth_client(owner)
    response = client.post(
        create_url(space),
        {"source_type": "wechat", "idempotency_key": "async-batch"},
        format="json",
    )
    batch = UploadBatch.objects.get(pk=response.data["data"]["id"])
    client.put(
        batch_url(batch, "archive"),
        {"archive": archive_file(build_archive())},
        format="multipart",
    )
    settings.CHAT_UPLOAD_PARSE_INLINE = False
    with (
        patch("chat_ingestion.views.dispatch_parse_chat_upload") as dispatch,
        patch(
            "chat_ingestion.views.transaction.on_commit",
            side_effect=lambda callback: callback(),
        ),
    ):
        completed = client.post(batch_url(batch, "complete"))

    assert completed.status_code == 202
    assert completed.data["data"]["status"] == UploadBatch.Status.PROCESSING
    dispatch.assert_called_once()
    assert UploadBatch.objects.get(pk=batch.pk).status == (
        UploadBatch.Status.PROCESSING
    )


def test_cancelled_upload_is_terminal():
    owner = User.objects.create_user(username="upload-cancel-owner")
    space = make_team(owner, slug="upload-cancel-team")
    client = auth_client(owner)
    response = client.post(
        create_url(space),
        {"source_type": "wechat", "idempotency_key": "cancel-batch"},
        format="json",
    )
    batch = UploadBatch.objects.get(pk=response.data["data"]["id"])

    cancelled = client.post(batch_url(batch, "cancel"))
    repeated = client.post(batch_url(batch, "cancel"))

    assert cancelled.status_code == 200
    assert cancelled.data["data"]["status"] == UploadBatch.Status.CANCELLED
    assert repeated.status_code == 200
    assert client.post(batch_url(batch, "complete")).status_code == 409
    archive = client.put(
        batch_url(batch, "archive"),
        {"archive": archive_file()},
        format="multipart",
    )
    assert archive.status_code == 409
    assert (
        SpaceAuditLog.objects.filter(
            action="chat.upload_cancelled", resource_id=str(batch.pk)
        ).count()
        == 1
    )


def test_archived_space_rejects_upload_mutations():
    owner = User.objects.create_user(username="upload-archived-owner")
    space = make_team(owner, slug="upload-archived-team")
    client = auth_client(owner)
    response = client.post(
        create_url(space),
        {"source_type": "wechat", "idempotency_key": "archived-batch"},
        format="json",
    )
    batch = UploadBatch.objects.get(pk=response.data["data"]["id"])
    client.put(
        batch_url(batch, "archive"),
        {"archive": archive_file()},
        format="multipart",
    )
    space.status = Space.Status.ARCHIVED
    space.save(update_fields=("status", "updated_at"))

    archive = client.put(
        batch_url(batch, "archive"),
        {"archive": archive_file(b"second-package")},
        format="multipart",
    )
    complete = client.post(batch_url(batch, "complete"))
    cancel = client.post(batch_url(batch, "cancel"))

    assert archive.status_code == 409
    assert complete.status_code == 409
    assert cancel.status_code == 409
    batch.refresh_from_db()
    assert batch.status == UploadBatch.Status.UPLOADING


def test_staff_admin_must_take_over_before_operating():
    owner = User.objects.create_user(username="upload-admin-owner")
    admin = User.objects.create_user(username="upload-admin", is_staff=True)
    space = make_team(owner, slug="upload-admin-team")
    response = auth_client(owner).post(
        create_url(space),
        {"source_type": "wechat", "idempotency_key": "admin-batch"},
        format="json",
    )
    batch = UploadBatch.objects.get(pk=response.data["data"]["id"])
    admin_client = auth_client(admin)

    denied = admin_client.put(
        batch_url(batch, "archive"),
        {"archive": archive_file()},
        format="multipart",
    )
    assert denied.status_code == 404

    SpaceTakeover.objects.create(space=space, admin=admin, reason="audit")
    allowed = admin_client.put(
        batch_url(batch, "archive"),
        {"archive": archive_file()},
        format="multipart",
    )
    assert allowed.status_code == 200
    audit = SpaceAuditLog.objects.get(
        action="chat.archive_uploaded", resource_id=str(batch.pk)
    )
    assert audit.metadata["takeover_id"] is not None


@pytest.mark.unit
def test_batch_state_machine_rejects_skipped_steps():
    owner = User.objects.create_user(username="upload-machine-owner")
    space = make_team(owner, slug="upload-machine-team")
    batch = UploadBatch.objects.create(
        space=space,
        uploaded_by=owner,
        source_type=UploadBatch.SourceType.WECHAT,
        idempotency_key="machine-batch",
    )

    with pytest.raises(UploadTransitionError):
        transition_batch(batch, UploadBatch.Status.PROCESSING)
    with pytest.raises(UploadTransitionError):
        transition_batch(batch, UploadBatch.Status.CREATED)

    transition_batch(batch, UploadBatch.Status.UPLOADING)
    transition_batch(batch, UploadBatch.Status.PROCESSING)
    transition_batch(batch, UploadBatch.Status.COMPLETED)
    batch.refresh_from_db()
    assert batch.status == UploadBatch.Status.COMPLETED
    assert batch.completed_at is not None
    with pytest.raises(UploadTransitionError):
        transition_batch(batch, UploadBatch.Status.UPLOADING)


@patch("chat_ingestion.views._enqueue_parse")
def test_failed_upload_can_be_retried_and_item_is_readable(enqueue):
    owner = User.objects.create_user(username="upload-retry-owner")
    space = make_team(owner, slug="upload-retry-team")
    client = auth_client(owner)
    response = client.post(
        create_url(space), payload("retry-batch"), format="json"
    )
    batch = UploadBatch.objects.get(pk=response.data["data"]["id"])
    batch.status = UploadBatch.Status.FAILED
    batch.error_message = "temporary parser failure"
    batch.save(update_fields=("status", "error_message", "updated_at"))
    enqueue.return_value = {"status": UploadBatch.Status.PROCESSING}
    retried = client.post(batch_url(batch, "retry"))
    batch.refresh_from_db()
    assert retried.status_code == 202
    assert batch.status == UploadBatch.Status.UPLOADING
    enqueue.assert_called_once_with(batch)

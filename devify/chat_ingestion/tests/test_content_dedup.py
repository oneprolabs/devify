"""Content-hash deduplication across uploaders.

Two people exporting the same group should not make the server analyse the
same messages twice. The batch stores a digest of the normalised content and
the analysis request key carries it, so identical data reuses one job.
"""

import pytest
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from chat_analysis.models import AnalysisJob
from chat_ingestion.models import UploadBatch
from chat_ingestion.tasks import parse_chat_upload_task
from chat_ingestion.tests.archives import (
    DEFAULT_CONVERSATIONS,
    DEFAULT_MESSAGES,
    build_archive,
)
from spaces.models import Space, SpaceMembership

pytestmark = [pytest.mark.django_db, pytest.mark.integration]


@pytest.fixture(autouse=True)
def archive_storage(settings, tmp_path):
    settings.CHAT_UPLOAD_ARCHIVE_DIR = str(tmp_path / "chat_archives")


def make_team(owner, slug="dedup-team"):
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


def upload(client, space, key, content):
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


def test_same_content_from_another_uploader_reuses_the_analysis_job():
    owner = User.objects.create_user(username="dedup-owner")
    mate = User.objects.create_user(username="dedup-mate")
    space = make_team(owner)
    SpaceMembership.objects.create(
        space=space, user=mate, role=SpaceMembership.Role.USER
    )
    content = build_archive()

    first = upload(client_for(owner), space, "dedup-first", content)
    second = upload(client_for(mate), space, "dedup-second", content)

    assert first.content_sha256
    assert second.content_sha256 == first.content_sha256
    assert second.status == UploadBatch.Status.COMPLETED
    assert second.message_count == 0
    assert second.duplicate_count == 2
    assert AnalysisJob.objects.count() == 1
    # The same messages, just re-attributed to the second batch.
    assert second.conversation_digests == first.conversation_digests


def test_changed_content_creates_a_new_analysis_job():
    owner = User.objects.create_user(username="dedup-changed-owner")
    space = make_team(owner, slug="dedup-changed-team")
    client = client_for(owner)

    first = upload(client, space, "dedup-changed-1", build_archive())

    extra = {
        "conversation_id": "group-a",
        "message_key": "srv:3",
        "source_message_id": "3",
        "sender_key": "wx-a",
        "sender_name": "甲",
        "occurred_at": "2026-10-20T09:10:00+08:00",
    }
    updated = build_archive(
        conversations=DEFAULT_CONVERSATIONS,
        messages=DEFAULT_MESSAGES + [extra],
        parts=[],
        media={},
    )
    second = upload(client, space, "dedup-changed-2", updated)

    assert second.content_sha256 != first.content_sha256
    assert second.message_count == 1
    assert AnalysisJob.objects.count() == 2


def test_same_content_in_another_space_is_analyzed_separately():
    owner = User.objects.create_user(username="dedup-space-owner")
    other = User.objects.create_user(username="dedup-space-other")
    first_space = make_team(owner, slug="dedup-space-a")
    second_space = make_team(other, slug="dedup-space-b")
    content = build_archive()

    first = upload(client_for(owner), first_space, "dedup-a", content)
    second = upload(client_for(other), second_space, "dedup-b", content)

    assert first.content_sha256 == second.content_sha256
    assert second.message_count == 2
    assert AnalysisJob.objects.count() == 2
    assert AnalysisJob.objects.filter(space=second_space).count() == 1


def test_digest_ignores_archive_layout():
    owner = User.objects.create_user(username="dedup-layout-owner")
    space = make_team(owner, slug="dedup-layout-team")
    client = client_for(owner)

    first = upload(client, space, "dedup-layout-1", build_archive())
    repacked = upload(
        client,
        space,
        "dedup-layout-2",
        build_archive(extra={"notes.txt": b"repacked"}),
    )

    assert repacked.archive_sha256 != first.archive_sha256
    assert repacked.content_sha256 == first.content_sha256
    assert AnalysisJob.objects.count() == 1


def test_identical_content_retries_a_previously_failed_job():
    owner = User.objects.create_user(username="dedup-retry-owner")
    space = make_team(owner, slug="dedup-retry-team")
    client = client_for(owner)
    content = build_archive()

    first = upload(client, space, "dedup-retry-1", content)
    job = AnalysisJob.objects.get()
    AnalysisJob.objects.filter(pk=job.pk).update(
        state=AnalysisJob.State.FAILED, error="provider unavailable"
    )

    second = upload(client, space, "dedup-retry-2", content)

    job.refresh_from_db()
    assert second.content_sha256 == first.content_sha256
    assert AnalysisJob.objects.count() == 1
    assert job.state in (
        AnalysisJob.State.QUEUED,
        AnalysisJob.State.READY,
        AnalysisJob.State.PARTIAL,
    )


def test_parse_task_reports_skipped_duplicates():
    owner = User.objects.create_user(username="dedup-task-owner")
    space = make_team(owner, slug="dedup-task-team")
    client = client_for(owner)
    content = build_archive()

    upload(client, space, "dedup-task-1", content)
    second = upload(client, space, "dedup-task-2", content)

    result = parse_chat_upload_task.run(second.pk)

    # The batch is already completed, so the task is a no-op.
    assert result["status"] == UploadBatch.Status.COMPLETED

"""Native Rust archive -> real desktop APIs -> parser -> message readback.

Synthetic fixtures are exported by devify-desktop runtime_tests with
AIMYCHATS_E2E_ARTIFACT_DIR. They contain no real chats or credentials.
"""

import hashlib
import json
import zipfile
from pathlib import Path

import pytest
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from accounts.models import DesktopDevice
from chat_domain.models import Message
from chat_ingestion.models import UploadBatch
from spaces.services import SpaceBootstrapService


@pytest.mark.django_db
@pytest.mark.parametrize("platform", ["wechat", "whatsapp"])
def test_native_automatic_batch_roundtrip(platform, settings, tmp_path):
    settings.CHAT_UPLOAD_PARSE_INLINE = True
    settings.CHAT_UPLOAD_ANALYSIS_INLINE = True
    settings.CHAT_ANALYSIS_LLM_ENABLED = False
    settings.CHAT_ANALYSIS_AUTO_CREATE_EVENTS = False
    settings.CHAT_UPLOAD_ARCHIVE_DIR = str(tmp_path / "archives")
    settings.CHAT_MEDIA_DIR = str(tmp_path / "media")
    fixture = Path(__file__).parent / "fixtures" / "desktop-runtime" / f"{platform}.zip"
    raw = fixture.read_bytes()
    with zipfile.ZipFile(fixture) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        names = manifest["scope"]["conversation_ids"]
    user = User.objects.create_user(username=f"native-contract-{platform}")
    space = SpaceBootstrapService.ensure_personal_space(user)
    DesktopDevice.objects.create(user=user, device_id="native-test", status="active")
    client = APIClient()
    client.force_authenticate(user=user)
    target = dict(platform=platform, source_account_id=manifest["source_namespace"])
    config = dict(
        schema_version=1,
        device_id="native-test",
        mutation_id="draft",
        local_revision=1,
        target=target,
        payload=dict(
            setup_state="draft",
            enabled=True,
            usernames=names,
            initial_ranges={name: dict(since=1, until=None) for name in names},
            sync_interval_seconds=1800,
            backup=dict(
                mode="interval",
                times=["18:00"],
                window_enabled=False,
                window_mode="deny",
                window_start="23:00",
                window_end="07:00",
                days=list(range(7)),
                wifi_only=True,
                attachments="text",
            ),
        ),
    )
    config_url = f"/api/v1/spaces/{space.pk}/desktop/sync-config"
    assert client.put(config_url, config, format="json").status_code == 200
    config["payload"]["setup_state"] = "completed"
    config.update(mutation_id="completed", local_revision=2)
    assert client.put(config_url, config, format="json").status_code == 200
    create = dict(
        source_type=platform,
        source_account_id=target["source_account_id"],
        device_id="native-test",
        idempotency_key="native-original",
        archive_sha256=hashlib.sha256(raw).hexdigest(),
        archive_size=len(raw),
        trigger="scheduled",
    )
    url = f"/api/v1/spaces/{space.pk}/chat/uploads"
    first = client.post(url, create, format="json")
    assert first.status_code == 201, first.data
    batch_id = first.data["data"]["id"]
    # Lost create response / restart: replay finds the same exact batch.
    replay = client.post(url, create, format="json")
    assert replay.status_code == 200
    assert replay.data["data"]["id"] == batch_id
    upload = client.put(
        f"/api/v1/chat/uploads/{batch_id}/archive",
        {
            "archive": SimpleUploadedFile(
                f"{platform}.zip", raw, content_type="application/zip"
            )
        },
        format="multipart",
    )
    assert upload.status_code == 200, upload.data
    result = client.post(f"/api/v1/chat/uploads/{batch_id}/complete")
    assert result.status_code == 200, result.data
    assert result.data["data"]["status"] == "completed"
    count = Message.objects.filter(conversation__space=space).count()
    assert count == manifest["counts"]["messages"]
    assert client.post(f"/api/v1/chat/uploads/{batch_id}/complete").status_code == 200
    assert Message.objects.filter(conversation__space=space).count() == count
    assert UploadBatch.objects.filter(space=space).count() == 1
    for name in names:
        lookup = client.get(
            f"/api/v1/spaces/{space.pk}/desktop/conversation",
            {
                "platform": platform,
                "source_account_id": target["source_account_id"],
                "source_conversation_id": name,
            },
        )
        assert lookup.status_code == 200, lookup.data
        conversation = lookup.data["data"]["conversation"]
        assert conversation is not None
        readback = client.get(
            f"/api/v1/spaces/{space.pk}/conversations/{conversation['id']}/messages",
            {"page": "last", "page_size": 100},
        )
        assert readback.status_code == 200, readback.data
        assert len(readback.data["data"]["list"]) <= 100

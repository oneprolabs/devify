import copy
import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from accounts.models import DesktopDevice
from spaces.models import DesktopBackupConfig, DesktopConfigReceipt
from spaces.services import SpaceBootstrapService

pytestmark = pytest.mark.django_db


@pytest.fixture
def fixture():
    user = User.objects.create_user(username="desktop-config-owner")
    space = SpaceBootstrapService.ensure_personal_space(user)
    DesktopDevice.objects.create(user=user, device_id="desktop", status="active")
    client = APIClient()
    client.force_authenticate(user=user)
    payload = dict(
        schema_version=1,
        device_id="desktop",
        mutation_id="mutation-1",
        local_revision=1,
        target=dict(platform="wechat", source_account_id="local-source"),
        payload=dict(
            setup_state="completed",
            enabled=True,
            usernames=["chat"],
            initial_ranges={"chat": dict(since=100, until=None)},
            sync_interval_seconds=1800,
            backup=dict(
                mode="interval",
                times=["18:00"],
                window_enabled=False,
                window_mode="deny",
                window_start="23:00",
                window_end="07:00",
                days=[0, 1, 2, 3, 4, 5, 6],
                wifi_only=True,
                attachments="text",
            ),
        ),
    )
    return client, space, payload


def test_save_and_lost_response_retry_do_not_reapply_old_settings(fixture):
    client, space, payload = fixture
    url = f"/api/v1/spaces/{space.pk}/desktop/sync-config"
    first = client.put(url, payload, format="json")
    assert first.status_code == 200, first.data
    newer = copy.deepcopy(payload)
    newer.update(mutation_id="mutation-2", local_revision=2)
    newer["payload"]["enabled"] = False
    assert client.put(url, newer, format="json").status_code == 200
    assert client.put(url, payload, format="json").data == first.data
    assert DesktopBackupConfig.objects.get().completed["enabled"] is False
    assert DesktopConfigReceipt.objects.count() == 2


def test_draft_keeps_completed_config_and_other_target(fixture):
    client, space, payload = fixture
    url = f"/api/v1/spaces/{space.pk}/desktop/sync-config"
    assert client.put(url, payload, format="json").status_code == 200
    draft = copy.deepcopy(payload)
    draft["mutation_id"] = "draft"
    draft["payload"]["setup_state"] = "draft"
    draft["payload"]["usernames"] = []
    draft["payload"]["initial_ranges"] = {}
    assert client.put(url, draft, format="json").status_code == 200
    row = DesktopBackupConfig.objects.get()
    assert row.completed["usernames"] == ["chat"]
    assert row.draft["usernames"] == []
    other = copy.deepcopy(payload)
    other["mutation_id"] = "whatsapp"
    other["target"]["platform"] = "whatsapp"
    assert client.put(url, other, format="json").status_code == 200
    assert DesktopBackupConfig.objects.count() == 2


def test_secrets_unknown_fields_and_key_reuse_rejected(fixture):
    client, space, payload = fixture
    url = f"/api/v1/spaces/{space.pk}/desktop/sync-config"
    for field in ["enc_key", "key_ref", "path"]:
        bad = copy.deepcopy(payload)
        bad["payload"][field] = "secret"
        assert client.put(url, bad, format="json").status_code == 400
    assert client.put(url, payload, format="json").status_code == 200
    changed = copy.deepcopy(payload)
    changed["payload"]["enabled"] = False
    assert client.put(url, changed, format="json").status_code == 409
    assert DesktopBackupConfig.objects.get().completed["enabled"] is True


def test_scope_and_device_authorization(fixture):
    client, space, payload = fixture
    url = f"/api/v1/spaces/{space.pk}/desktop/sync-config"
    payload["device_id"] = "someone-else"
    assert client.put(url, payload, format="json").status_code == 403
    outsider = User.objects.create_user(username="desktop-config-outsider")
    client.force_authenticate(user=outsider)
    assert client.put(url, payload, format="json").status_code == 404
    assert DesktopBackupConfig.objects.count() == 0


def test_opaque_conversation_keys_are_not_transformed(fixture):
    client, space, payload = fixture
    payload["payload"]["usernames"] = ["wxid_Test_123", "44987027346@chatroom"]
    payload["payload"]["initial_ranges"] = {
        "wxid_Test_123": {"since": 100, "until": None}
    }
    response = client.put(
        f"/api/v1/spaces/{space.pk}/desktop/sync-config", payload, format="json"
    )
    assert response.status_code == 200, response.data
    assert (
        "wxid_Test_123" in DesktopBackupConfig.objects.get().completed["initial_ranges"]
    )


def test_precise_recovery_is_scoped_to_owner_device_and_source(fixture):
    from chat_ingestion.models import UploadBatch

    client, space, payload = fixture
    user = space.owner
    batch = UploadBatch.objects.create(
        space=space,
        uploaded_by=user,
        source_type="wechat",
        source_account_id="local-source",
        device_id="desktop",
        idempotency_key="original",
        status="uploading",
    )
    url = f"/api/v1/spaces/{space.pk}/chat/uploads/recovery"
    args = {
        "device_id": "desktop",
        "source_account_id": "local-source",
        "idempotency_key": "original",
    }
    response = client.get(url, args)
    assert response.status_code == 200, response.data
    assert response.data["data"]["batch"]["id"] == batch.pk
    args["source_account_id"] = "other-source"
    assert client.get(url, args).data["data"]["batch"] is None
    args["device_id"] = "foreign-device"
    assert client.get(url, args).status_code == 403


def test_existing_upload_retry_ignores_new_upload_quota(fixture):
    from unittest.mock import patch

    client, space, data = fixture
    url = f"/api/v1/spaces/{space.pk}/chat/uploads"
    payload = {
        "source_type": "wechat",
        "source_account_id": "local-source",
        "device_id": "desktop",
        "idempotency_key": "original",
        "archive_sha256": "a" * 64,
        "archive_size": 123,
    }
    first = client.post(url, payload, format="json")
    assert first.status_code == 201, first.data
    with patch("chat_ingestion.views.check_storage_quota", return_value="full"):
        retry = client.post(url, payload, format="json")
        assert retry.status_code == 200, retry.data
        assert retry.data["data"]["id"] == first.data["data"]["id"]
        payload["idempotency_key"] = "new"
        assert client.post(url, payload, format="json").status_code == 413


def test_batch_key_lookup_preserves_namespace_and_bounds(fixture):
    from chat_domain.models import Conversation, Message
    from django.utils import timezone

    client, space, _ = fixture
    c = Conversation.objects.create(
        space=space,
        platform="wechat",
        source_namespace="local-source",
        source_conversation_id="chat",
        identity_key="wechat:chat",
    )
    Message.objects.create(
        conversation=c, message_key="src:1", ingest_seq=1, occurred_at=timezone.now()
    )
    url = f"/api/v1/spaces/{space.pk}/desktop/message-keys"
    payload = {
        "source_account_id": "local-source",
        "queries": [{"username": "chat", "keys": ["src:1", "src:2"]}],
    }
    response = client.post(url, payload, format="json")
    assert response.status_code == 200, response.data
    assert [row["message_key"] for row in response.data["data"]["list"][0]["keys"]] == [
        "src:1"
    ]
    payload["source_account_id"] = "another-account"
    assert (
        client.post(url, payload, format="json").data["data"]["list"][0]["keys"] == []
    )
    payload["queries"][0]["keys"] = ["k"] * 1001
    assert client.post(url, payload, format="json").status_code == 400

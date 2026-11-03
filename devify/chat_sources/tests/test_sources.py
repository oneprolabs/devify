import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from chat_sources.models import Source, SourceImport
from spaces.models import Space, SpaceMembership

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


def test_manager_can_create_source_and_capabilities_are_explicit():
    owner = User.objects.create_user(username="source-owner")
    space = make_space(owner, "source-team")
    client = APIClient()
    client.force_authenticate(user=owner)

    response = client.post(
        f"/api/v1/spaces/{space.pk}/sources",
        {
            "channel_type": "wechat",
            "provider": "tauri_upload",
            "external_account_key": "wxid-1",
            "display_name": "My WeChat",
        },
        format="json",
    )

    assert response.status_code == 201
    assert response.data["data"]["capabilities"] == [
        "file_import",
        "attachments",
    ]
    assert Source.objects.filter(space=space).count() == 1


def test_unverified_channel_does_not_claim_capabilities():
    owner = User.objects.create_user(username="source-unsupported")
    space = make_space(owner, "source-unsupported-team")
    client = APIClient()
    client.force_authenticate(user=owner)

    response = client.post(
        f"/api/v1/spaces/{space.pk}/sources",
        {
            "channel_type": "whatsapp",
            "provider": "tauri_upload",
            "external_account_key": "wa-1",
            "display_name": "WhatsApp",
        },
        format="json",
    )

    assert response.status_code == 201
    assert response.data["data"]["capabilities"] == []


def test_guest_can_read_but_cannot_manage_sources():
    owner = User.objects.create_user(username="source-guest-owner")
    guest = User.objects.create_user(username="source-guest")
    space = make_space(owner, "source-guest-team")
    SpaceMembership.objects.create(
        space=space,
        user=guest,
        role=SpaceMembership.Role.GUEST,
    )
    Source.objects.create(
        space=space,
        channel_type=Source.ChannelType.WECHAT,
        provider="tauri_upload",
        external_account_key="wxid-guest",
        display_name="WeChat",
        capabilities=["file_import"],
        created_by=owner,
        updated_by=owner,
    )
    client = APIClient()
    client.force_authenticate(user=guest)

    assert client.get(f"/api/v1/spaces/{space.pk}/sources").status_code == 200
    assert (
        client.post(
            f"/api/v1/spaces/{space.pk}/sources",
            {
                "channel_type": "wechat",
                "provider": "tauri_upload",
                "external_account_key": "wxid-new",
                "display_name": "New",
            },
            format="json",
        ).status_code
        == 404
    )


def test_source_import_stays_in_the_same_space():
    owner = User.objects.create_user(username="source-import-owner")
    space = make_space(owner, "source-import-team")
    source = Source.objects.create(
        space=space,
        channel_type=Source.ChannelType.WECHAT,
        provider="tauri_upload",
        external_account_key="wxid-import",
        display_name="WeChat",
        created_by=owner,
        updated_by=owner,
    )
    with pytest.raises(Exception):
        SourceImport.objects.create(
            space=make_space(owner, "source-other-team"),
            source=source,
            initiated_by=owner,
        )


def test_source_status_verify_and_jobs_are_explicit_for_local_upload():
    owner = User.objects.create_user(username="source-status-owner")
    space = make_space(owner, "source-status-team")
    source = Source.objects.create(space=space, channel_type=Source.ChannelType.WECHAT, provider="tauri_upload", external_account_key="wxid-status", display_name="WeChat", capabilities=["file_import"], created_by=owner, updated_by=owner)
    client = APIClient()
    client.force_authenticate(user=owner)
    verify = client.post(f"/api/v1/sources/{source.pk}/verify")
    assert verify.status_code == 200
    assert verify.data["data"]["verified"] is False
    assert verify.data["data"]["status"] == "not_applicable"
    status = client.get(f"/api/v1/sources/{source.pk}/status")
    assert status.status_code == 200
    assert status.data["data"]["capabilities"] == ["file_import"]
    assert client.get(f"/api/v1/sources/{source.pk}/jobs").data["data"] == []

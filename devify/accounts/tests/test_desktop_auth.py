import base64
import hashlib
import secrets
from urllib.parse import parse_qs, urlparse

import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from accounts.models import DesktopDevice

pytestmark = pytest.mark.django_db


def challenge(verifier):
    digest = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


def test_desktop_code_exchange_requires_pkce_and_is_one_time():
    user = User.objects.create_user(
        username="desktop-auth-user", password="secret"
    )
    client = APIClient()
    client.force_authenticate(user=user)
    verifier = secrets.token_urlsafe(32)
    state = secrets.token_urlsafe(12)
    authorize = client.get(
        "/api/v1/auth/desktop/authorize",
        {
            "client_id": "desktop-client",
            "redirect_uri": "http://127.0.0.1:47832/auth/callback",
            "response_type": "code",
            "state": state,
            "code_challenge": challenge(verifier),
            "code_challenge_method": "S256",
            "device_label": "Test Mac",
        },
    )
    assert authorize.status_code == 302
    callback = urlparse(authorize["Location"])
    query = parse_qs(callback.query)
    assert query["state"] == [state]
    assert "access" not in query
    assert "refresh" not in query

    exchanged = client.post(
        "/api/v1/auth/desktop/token",
        {
            "grant_type": "authorization_code",
            "client_id": "desktop-client",
            "redirect_uri": "http://127.0.0.1:47832/auth/callback",
            "code": query["code"][0],
            "code_verifier": verifier,
        },
        format="json",
    )
    assert exchanged.status_code == 200
    assert exchanged.data["access"]
    assert exchanged.data["refresh"]
    assert exchanged.data["device_label"] == "Test Mac"
    device_id = exchanged.data["device_id"]
    assert DesktopDevice.objects.filter(
        user=user, device_id=device_id, status=DesktopDevice.Status.ACTIVE
    ).exists()

    client.credentials(HTTP_AUTHORIZATION=f"Bearer {exchanged.data['access']}")
    devices = client.get("/api/v1/auth/desktop/devices")
    assert devices.status_code == 200
    assert devices.data["data"][0]["device_id"] == device_id
    assert (
        client.delete(f"/api/v1/auth/desktop/devices/{device_id}").status_code
        == 204
    )
    client.force_authenticate(user=None)
    assert client.get("/api/v1/auth/user").status_code == 401

    replay = client.post(
        "/api/v1/auth/desktop/token",
        {
            "grant_type": "authorization_code",
            "client_id": "desktop-client",
            "redirect_uri": "http://127.0.0.1:47832/auth/callback",
            "code": query["code"][0],
            "code_verifier": verifier,
        },
        format="json",
    )
    assert replay.status_code == 400


def test_desktop_code_exchange_rejects_wrong_verifier():
    user = User.objects.create_user(username="desktop-auth-pkce")
    client = APIClient()
    client.force_authenticate(user=user)
    verifier = secrets.token_urlsafe(32)
    response = client.get(
        "/api/v1/auth/desktop/authorize",
        {
            "client_id": "desktop-client",
            "redirect_uri": "http://127.0.0.1:47832/auth/callback",
            "response_type": "code",
            "state": "state",
            "code_challenge": challenge(verifier),
        },
    )
    code = parse_qs(urlparse(response["Location"]).query)["code"][0]
    exchange = client.post(
        "/api/v1/auth/desktop/token",
        {
            "grant_type": "authorization_code",
            "client_id": "desktop-client",
            "redirect_uri": "http://127.0.0.1:47832/auth/callback",
            "code": code,
            "code_verifier": "wrong",
        },
        format="json",
    )
    assert exchange.status_code == 400


def test_existing_login_can_register_and_refresh_its_device():
    user = User.objects.create_user(username="desktop-register-user")
    client = APIClient()
    client.force_authenticate(user=user)

    first = client.post(
        "/api/v1/auth/desktop/devices",
        {"label": "MacBook Pro", "platform": "macos"},
        format="json",
    )
    assert first.status_code == 201
    device_id = first.data["data"]["device_id"]
    assert first.data["data"]["platform"] == "macos"
    assert DesktopDevice.objects.filter(
        user=user, device_id=device_id, platform="macos"
    ).exists()

    second = client.post(
        "/api/v1/auth/desktop/devices",
        {
            "device_id": device_id,
            "label": "MacBook Pro · 工作",
            "platform": "macos",
        },
        format="json",
    )
    assert second.status_code == 201
    assert second.data["data"]["device_id"] == device_id
    assert DesktopDevice.objects.filter(user=user).count() == 1
    assert DesktopDevice.objects.get(user=user).label == "MacBook Pro · 工作"


def test_missing_device_row_does_not_block_the_token():
    user = User.objects.create_user(username="desktop-missing-device")
    token = AccessToken.for_user(user)
    token["device_id"] = "device-row-missing"
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    response = client.get("/api/v1/auth/desktop/devices")

    assert response.status_code == 200


def test_token_refresh_recreates_a_missing_device():
    user = User.objects.create_user(username="desktop-refresh-user")
    refresh = RefreshToken.for_user(user)
    refresh["device_id"] = "refresh-device-1"

    response = APIClient().post(
        "/api/v1/auth/token/refresh",
        {"refresh": str(refresh)},
        format="json",
    )

    assert response.status_code == 200
    assert DesktopDevice.objects.filter(
        user=user,
        device_id="refresh-device-1",
        status=DesktopDevice.Status.ACTIVE,
    ).exists()


def test_token_refresh_does_not_reactivate_a_revoked_device():
    user = User.objects.create_user(username="desktop-revoked-user")
    device = DesktopDevice.objects.create(
        user=user,
        device_id="revoked-device-1",
        status=DesktopDevice.Status.REVOKED,
    )
    refresh = RefreshToken.for_user(user)
    refresh["device_id"] = device.device_id

    response = APIClient().post(
        "/api/v1/auth/token/refresh",
        {"refresh": str(refresh)},
        format="json",
    )

    assert response.status_code == 200
    device.refresh_from_db()
    assert device.status == DesktopDevice.Status.REVOKED


def test_register_adopts_a_legacy_device_without_a_label():
    user = User.objects.create_user(username="desktop-legacy-device")
    legacy = DesktopDevice.objects.create(
        user=user,
        device_id="legacy-empty-device",
        label="",
        platform="",
        status=DesktopDevice.Status.ACTIVE,
    )
    client = APIClient()
    client.force_authenticate(user=user)

    response = client.post(
        "/api/v1/auth/desktop/devices",
        {"label": "MacOS27", "platform": "macos"},
        format="json",
    )

    assert response.status_code == 201
    assert response.data["data"]["device_id"] == legacy.device_id
    legacy.refresh_from_db()
    assert legacy.label == "MacOS27"
    assert legacy.platform == "macos"
    assert DesktopDevice.objects.filter(user=user).count() == 1

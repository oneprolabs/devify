import base64
import hashlib
import secrets
from urllib.parse import parse_qs, urlparse

import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from accounts.models import TauriDevice

pytestmark = pytest.mark.django_db


def challenge(verifier):
    digest = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


def test_tauri_code_exchange_requires_pkce_and_is_one_time():
    user = User.objects.create_user(
        username="tauri-auth-user", password="secret"
    )
    client = APIClient()
    client.force_authenticate(user=user)
    verifier = secrets.token_urlsafe(32)
    state = secrets.token_urlsafe(12)
    authorize = client.get(
        "/api/v1/auth/tauri/authorize",
        {
            "client_id": "wechat-devify-tauri",
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
        "/api/v1/auth/tauri/token",
        {
            "grant_type": "authorization_code",
            "client_id": "wechat-devify-tauri",
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
    assert TauriDevice.objects.filter(
        user=user, device_id=device_id, status=TauriDevice.Status.ACTIVE
    ).exists()

    client.credentials(HTTP_AUTHORIZATION=f"Bearer {exchanged.data['access']}")
    devices = client.get("/api/v1/auth/tauri/devices")
    assert devices.status_code == 200
    assert devices.data["data"][0]["device_id"] == device_id
    assert (
        client.delete(f"/api/v1/auth/tauri/devices/{device_id}").status_code
        == 204
    )
    client.force_authenticate(user=None)
    assert client.get("/api/v1/auth/user").status_code == 401

    replay = client.post(
        "/api/v1/auth/tauri/token",
        {
            "grant_type": "authorization_code",
            "client_id": "wechat-devify-tauri",
            "redirect_uri": "http://127.0.0.1:47832/auth/callback",
            "code": query["code"][0],
            "code_verifier": verifier,
        },
        format="json",
    )
    assert replay.status_code == 400


def test_tauri_code_exchange_rejects_wrong_verifier():
    user = User.objects.create_user(username="tauri-auth-pkce")
    client = APIClient()
    client.force_authenticate(user=user)
    verifier = secrets.token_urlsafe(32)
    response = client.get(
        "/api/v1/auth/tauri/authorize",
        {
            "client_id": "wechat-devify-tauri",
            "redirect_uri": "http://127.0.0.1:47832/auth/callback",
            "response_type": "code",
            "state": "state",
            "code_challenge": challenge(verifier),
        },
    )
    code = parse_qs(urlparse(response["Location"]).query)["code"][0]
    exchange = client.post(
        "/api/v1/auth/tauri/token",
        {
            "grant_type": "authorization_code",
            "client_id": "wechat-devify-tauri",
            "redirect_uri": "http://127.0.0.1:47832/auth/callback",
            "code": code,
            "code_verifier": "wrong",
        },
        format="json",
    )
    assert exchange.status_code == 400

import pytest
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db


def test_tauri_config_discovery_returns_public_protocol_metadata():
    response = APIClient().get("/api/v1/auth/tauri/config")
    assert response.status_code == 200
    data = response.data["data"]
    assert data["protocol_version"] == "oauth2-pkce.v1"
    assert data["client_id"] == "wechat-devify-tauri"
    assert data["redirect_uri"].startswith("http://127.0.0.1:")
    assert "token" not in data

from urllib.parse import parse_qs, urlparse

import pytest
from django.contrib.auth.models import User
from django.test import Client

pytestmark = pytest.mark.django_db


def _callback(client, next_path=None):
    params = {} if next_path is None else {"next": next_path}
    response = client.get("/accounts/oauth/callback/", params)
    assert response.status_code == 302
    return urlparse(response["Location"])


@pytest.fixture
def signed_in_client():
    user = User.objects.create_user(
        username="oauth-next-user", password="secret"
    )
    client = Client()
    client.force_login(user)
    return client


def test_callback_keeps_desktop_authorize_path(signed_in_client):
    next_path = (
        "/auth/desktop/authorize?client_id=desktop-client"
        "&response_type=code&state=state-value&code_challenge=challenge"
    )

    location = _callback(signed_in_client, next_path)
    query = parse_qs(location.query)

    assert location.path == "/auth/oauth/callback"
    assert query["access_token"]
    assert query["refresh_token"]
    assert query["next"] == [next_path]


def test_callback_without_next_keeps_tokens_only(signed_in_client):
    query = parse_qs(_callback(signed_in_client).query)

    assert query["access_token"]
    assert "next" not in query


@pytest.mark.parametrize(
    "unsafe_next",
    [
        "https://evil.example/steal",
        "//evil.example/steal",
        "/\\evil.example/steal",
        "auth/desktop/authorize",
    ],
)
def test_callback_drops_unsafe_next_paths(signed_in_client, unsafe_next):
    query = parse_qs(_callback(signed_in_client, unsafe_next).query)

    assert query["access_token"]
    assert "next" not in query

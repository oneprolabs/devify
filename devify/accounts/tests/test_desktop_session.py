from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from unittest.mock import patch

import pytest
from django.contrib.auth.models import User
from django.db import connections
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import DesktopDevice, DesktopSession
from chat_analysis.models import Event
from spaces.services.bootstrap import SpaceBootstrapService

pytestmark = pytest.mark.django_db

CREATE = "/api/v1/auth/desktop/session"
REFRESH = f"{CREATE}/refresh"
USER = "/api/v1/auth/user"
DEVICE = "/api/v1/auth/desktop/devices"


@pytest.fixture
def device():
    user = User.objects.create_user(username="desktop-session-user")
    return DesktopDevice.objects.create(user=user, device_id="mac-test")


def legacy_client(user, device_id=None):
    refresh = RefreshToken.for_user(user)
    if device_id:
        refresh["device_id"] = device_id
    client = APIClient()
    use_access(client, str(refresh.access_token))
    return client, str(refresh)


def use_access(client, access):
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")


def create_session(device):
    client, _ = legacy_client(device.user)
    response = client.post(
        CREATE, {"device_id": device.device_id}, format="json"
    )
    assert response.status_code == 201
    payload = response.json()["data"]
    use_access(client, payload["access"])
    return client, payload


def refresh_input(device, payload):
    return {"device_id": device.device_id, "session": payload["session"]}


def test_existing_desktop_client_can_refresh_across_days(device):
    _, payload = create_session(device)
    args = refresh_input(device, payload)
    client = APIClient()
    for days in (2, 6):
        with patch.object(
            timezone, "now", return_value=timezone.now() + timedelta(days=days)
        ):
            response = client.post(REFRESH, args, format="json")
            assert response.status_code == 200
            assert response.json()["data"]["access"]
            assert "session" not in response.json()["data"]


def test_heartbeat_and_refresh_do_not_extend_idle_expiry(device):
    client, payload = create_session(device)
    args = refresh_input(device, payload)
    start = DesktopSession.objects.get(device=device).last_active_at
    with patch.object(timezone, "now", return_value=start + timedelta(days=6)):
        renewed = APIClient().post(REFRESH, args, format="json")
        assert renewed.status_code == 200
        use_access(client, renewed.json()["data"]["access"])
        assert client.post(
            DEVICE, {"device_id": device.device_id}, format="json"
        ).status_code == 201
    with patch.object(timezone, "now", return_value=start + timedelta(days=7)):
        response = APIClient().post(REFRESH, args, format="json")
        assert response.status_code == 401


@pytest.mark.parametrize("action", ["sign_out", "revoke_device"])
def test_revocation_invalidates_access_and_refresh(device, action):
    client, payload = create_session(device)
    args = refresh_input(device, payload)
    anonymous = APIClient()
    assert client.get(USER).status_code == 200
    if action == "sign_out":
        for _ in range(2):
            response = anonymous.delete(REFRESH, args, format="json")
            assert response.status_code == 204
    else:
        assert client.delete(f"{DEVICE}/{device.device_id}").status_code == 204
    assert anonymous.post(REFRESH, args, format="json").status_code == 401
    assert client.get(USER).status_code == 401


def test_device_and_session_credentials_are_bound(device):
    other = User.objects.create_user(username="desktop-session-other")
    client, _ = legacy_client(other)
    assert client.post(
        CREATE, {"device_id": device.device_id}, format="json"
    ).status_code == 403
    client, _ = legacy_client(device.user, device.device_id)
    DesktopDevice.objects.create(user=device.user, device_id="another-mac")
    assert client.post(
        CREATE, {"device_id": "another-mac"}, format="json"
    ).status_code == 403
    _, payload = create_session(device)
    args = refresh_input(device, payload)
    assert APIClient().post(
        REFRESH, {**args, "device_id": "another-mac"}, format="json"
    ).status_code == 401
    assert APIClient().post(
        REFRESH, {**args, "session": "wrong"}, format="json"
    ).status_code == 401


def test_legacy_login_refresh_remains_available(device):
    client, refresh = legacy_client(device.user)
    assert client.get(USER).status_code == 200
    response = APIClient().post(
        "/api/v1/auth/token/refresh", {"refresh": refresh}, format="json"
    )
    assert response.status_code == 200
    assert response.json()["data"]["access"]


def test_manual_event_update_extends_session(device):
    client, payload = create_session(device)
    args = refresh_input(device, payload)
    start = DesktopSession.objects.get(device=device).last_active_at
    event = Event.objects.create(
        space=SpaceBootstrapService.ensure_personal_space(device.user),
        created_by=device.user,
        title="Desktop session test event",
        event_key="desktop-session-test",
        content="",
    )
    url = reverse("chat-event-detail", kwargs={"event_id": event.pk})
    with patch.object(timezone, "now", return_value=start + timedelta(days=6)):
        renewed = APIClient().post(REFRESH, args, format="json")
        assert renewed.status_code == 200
        use_access(client, renewed.json()["data"]["access"])
        assert client.patch(
            url, {"status": Event.Status.DONE}, format="json"
        ).status_code == 200

    with patch.object(timezone, "now", return_value=start + timedelta(days=8)):
        response = APIClient().post(REFRESH, args, format="json")
        assert response.status_code == 200
    with patch.object(
        timezone, "now", return_value=start + timedelta(days=13)
    ):
        response = APIClient().post(REFRESH, args, format="json")
        assert response.status_code == 401


def test_new_login_replaces_previous_session(device):
    previous_client, previous = create_session(device)
    assert previous_client.post(
        CREATE, {"device_id": device.device_id}, format="json"
    ).status_code == 403

    client, current = create_session(device)
    anonymous = APIClient()
    old_args = refresh_input(device, previous)
    response = anonymous.delete(REFRESH, old_args, format="json")
    assert response.status_code == 204
    assert anonymous.post(REFRESH, old_args, format="json").status_code == 401
    assert previous_client.get(USER).status_code == 401
    assert client.get(USER).status_code == 200
    assert anonymous.post(
        REFRESH, refresh_input(device, current), format="json"
    ).status_code == 200


@pytest.mark.django_db(transaction=True)
def test_old_logout_can_race_with_login_on_the_same_device(device):
    _, old = create_session(device)
    args = refresh_input(device, old)
    barrier = Barrier(2)

    def concurrently(request):
        try:
            barrier.wait(timeout=5)
            return request()
        finally:
            connections.close_all()

    def logout():
        return APIClient().delete(REFRESH, args, format="json")

    def login():
        client, _ = legacy_client(device.user)
        return client.post(
            CREATE, {"device_id": device.device_id}, format="json"
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        ended = executor.submit(concurrently, logout)
        created = executor.submit(concurrently, login)
        assert ended.result().status_code == 204
        response = created.result()
        assert response.status_code == 201

    current = refresh_input(device, response.json()["data"])
    assert APIClient().post(
        REFRESH, args, format="json"
    ).status_code == 401
    assert APIClient().post(
        REFRESH, current, format="json"
    ).status_code == 200

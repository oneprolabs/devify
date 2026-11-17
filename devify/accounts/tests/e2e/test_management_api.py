import pytest
from django.conf import settings
from django.contrib.auth.models import Group, User
from django.urls import reverse
from rest_framework.test import APIClient

from threadline.models import EmailAlias
from threadline.models import Settings as ThreadlineSettings


@pytest.mark.django_db
@pytest.mark.e2e
def test_management_create_user_bootstraps_related_resources():
    """Management API should bootstrap all user resources."""
    admin_user = User.objects.create_superuser(
        username="admin-user",
        email="admin@example.com",
        password="secret12345",
    )

    client = APIClient()
    client.force_authenticate(user=admin_user)

    response = client.post(
        reverse("management-users"),
        {
            "username": "managed-user",
            "email": "managed@example.com",
            "password": "secret12345",
            "first_name": "Managed",
            "last_name": "User",
            "is_staff": True,
            "is_active": True,
            "language": "zh-CN",
            "timezone": "Asia/Shanghai",
            "group_ids": [],
        },
        format="json",
    )

    assert response.status_code == 201

    user = User.objects.get(username="managed-user")
    profile = user.profile
    alias = EmailAlias.objects.get(user=user, is_active=True)
    prompt_config = ThreadlineSettings.objects.get(
        user=user,
        key="prompt_config",
        is_active=True,
    )
    email_config = ThreadlineSettings.objects.get(
        user=user,
        key="email_config",
        is_active=True,
    )

    assert profile.registration_completed is True
    assert profile.language == "zh-CN"
    assert profile.timezone == "Asia/Shanghai"
    assert alias.alias == "managed-user"
    assert alias.full_email_address() == (
        f"managed-user@{settings.AUTO_ASSIGN_EMAIL_DOMAIN}"
    )
    assert prompt_config.value["language"] == "zh-CN"
    assert prompt_config.value["scene"] == settings.DEFAULT_SCENE
    assert email_config.value == {"mode": "auto_assign"}


@pytest.mark.django_db
@pytest.mark.e2e
def test_management_list_users_returns_serialized_payloads():
    """Management API should serialize user rows, not None."""
    admin_user = User.objects.create_superuser(
        username="admin-user",
        email="admin@example.com",
        password="secret12345",
    )
    User.objects.create_user(
        username="listed-user",
        email="listed@example.com",
        password="secret12345",
        first_name="Listed",
        last_name="User",
    )

    client = APIClient()
    client.force_authenticate(user=admin_user)

    response = client.get(reverse("management-users"), {"page_size": 10})

    assert response.status_code == 200

    payload = response.json()["data"]
    assert payload["count"] == 2
    assert len(payload["results"]) == 2
    assert all(item is not None for item in payload["results"])
    usernames = {item["username"] for item in payload["results"]}
    assert usernames == {"admin-user", "listed-user"}


@pytest.mark.django_db
@pytest.mark.e2e
def test_management_update_user_fields_and_permissions():
    """Management API should update profile fields, flags and groups."""
    admin_user = User.objects.create_superuser(
        username="admin-user",
        email="admin@example.com",
        password="secret12345",
    )
    target = User.objects.create_user(
        username="target-user",
        email="target@example.com",
        password="secret12345",
    )
    group = Group.objects.create(name="support")

    client = APIClient()
    client.force_authenticate(user=admin_user)

    response = client.patch(
        reverse("management-user-detail", args=[target.pk]),
        {
            "email": "updated@example.com",
            "first_name": "Updated",
            "last_name": "User",
            "is_staff": True,
            "is_active": False,
            "language": "zh-CN",
            "timezone": "Asia/Shanghai",
            "group_ids": [group.pk],
            "password": "new-secret-12345",
        },
        format="json",
    )

    assert response.status_code == 200

    target.refresh_from_db()
    payload = response.json()["data"]
    assert payload["email"] == "updated@example.com"
    assert payload["display_name"] == "Updated User"
    assert payload["is_staff"] is True
    assert payload["is_active"] is False
    assert payload["language"] == "zh-CN"
    assert payload["timezone"] == "Asia/Shanghai"
    assert [item["id"] for item in payload["groups"]] == [group.pk]

    assert target.email == "updated@example.com"
    assert target.is_staff is True
    assert target.is_active is False
    assert target.check_password("new-secret-12345") is True
    assert list(target.groups.values_list("id", flat=True)) == [group.pk]
    assert target.profile.language == "zh-CN"
    assert target.profile.timezone == "Asia/Shanghai"


@pytest.mark.django_db
@pytest.mark.e2e
def test_management_update_user_rejects_username_change_and_taken_email():
    """Username is immutable; email must stay unique across users."""
    admin_user = User.objects.create_superuser(
        username="admin-user",
        email="admin@example.com",
        password="secret12345",
    )
    User.objects.create_user(
        username="existing-user",
        email="existing@example.com",
        password="secret12345",
    )
    target = User.objects.create_user(
        username="target-user",
        email="target@example.com",
        password="secret12345",
    )

    client = APIClient()
    client.force_authenticate(user=admin_user)
    url = reverse("management-user-detail", args=[target.pk])

    username_response = client.patch(
        url,
        {"username": "existing-user"},
        format="json",
    )
    assert username_response.status_code == 400
    assert username_response.json()["code"] == "username_immutable"

    email_response = client.patch(
        url,
        {"email": "existing@example.com"},
        format="json",
    )
    assert email_response.status_code == 400
    assert email_response.json()["code"] == "email_taken"

    # A user may keep its own username/email unchanged.
    same_response = client.patch(
        url,
        {"username": "target-user", "email": "target@example.com"},
        format="json",
    )
    assert same_response.status_code == 200


@pytest.mark.django_db
@pytest.mark.e2e
def test_management_admin_cannot_revoke_own_access():
    """Admins must not lock themselves out of the console."""
    admin_user = User.objects.create_superuser(
        username="admin-user",
        email="admin@example.com",
        password="secret12345",
    )

    client = APIClient()
    client.force_authenticate(user=admin_user)
    url = reverse("management-user-detail", args=[admin_user.pk])

    demote_response = client.patch(url, {"is_staff": False}, format="json")
    assert demote_response.status_code == 400
    assert demote_response.json()["code"] == "cannot_revoke_own_admin"

    deactivate_response = client.patch(
        url,
        {"is_active": False},
        format="json",
    )
    assert deactivate_response.status_code == 400
    assert deactivate_response.json()["code"] == "cannot_deactivate_self"

    admin_user.refresh_from_db()
    assert admin_user.is_staff is True
    assert admin_user.is_active is True


@pytest.mark.django_db
@pytest.mark.e2e
def test_management_update_user_requires_admin():
    """Non-admin users must not reach the user management endpoints."""
    regular_user = User.objects.create_user(
        username="regular-user",
        email="regular@example.com",
        password="secret12345",
    )
    target = User.objects.create_user(
        username="target-user",
        email="target@example.com",
        password="secret12345",
    )

    client = APIClient()
    client.force_authenticate(user=regular_user)

    response = client.patch(
        reverse("management-user-detail", args=[target.pk]),
        {"is_staff": True},
        format="json",
    )
    assert response.status_code == 403


@pytest.mark.django_db
@pytest.mark.e2e
def test_management_staff_cannot_modify_superuser():
    """A staff account must not reset a superuser password or deactivate it."""
    staff = User.objects.create_user(
        username="staff-admin",
        email="staff@example.com",
        password="secret12345",
        is_staff=True,
    )
    superuser = User.objects.create_superuser(
        username="root-user",
        email="root@example.com",
        password="secret12345",
    )

    client = APIClient()
    client.force_authenticate(user=staff)
    url = reverse("management-user-detail", args=[superuser.pk])

    for payload in (
        {"password": "attacker-secret"},
        {"is_active": False},
        {"is_staff": False},
    ):
        response = client.patch(url, payload, format="json")
        assert response.status_code == 403
        assert response.json()["code"] == "superuser_protected"

    superuser.refresh_from_db()
    assert superuser.check_password("secret12345") is True
    assert superuser.is_active is True
    assert superuser.is_staff is True


@pytest.mark.django_db
@pytest.mark.e2e
def test_management_rejects_malformed_group_ids_before_writing():
    """Invalid group ids return 400 instead of a 500 partial write."""
    admin_user = User.objects.create_superuser(
        username="admin-user",
        email="admin@example.com",
        password="secret12345",
    )
    target = User.objects.create_user(
        username="target-user",
        email="target@example.com",
        password="secret12345",
    )

    client = APIClient()
    client.force_authenticate(user=admin_user)
    url = reverse("management-user-detail", args=[target.pk])

    for group_ids in ("nope", ["abc"], [None], [{"a": 1}]):
        response = client.patch(
            url,
            {"email": "changed@example.com", "group_ids": group_ids},
            format="json",
        )
        assert response.status_code == 400
        assert response.json()["code"] == "invalid_group_ids"

    target.refresh_from_db()
    assert target.email == "target@example.com"

    create_response = client.post(
        reverse("management-users"),
        {
            "username": "bad-groups",
            "password": "secret12345",
            "group_ids": ["abc"],
        },
        format="json",
    )
    assert create_response.status_code == 400
    assert create_response.json()["code"] == "invalid_group_ids"
    assert not User.objects.filter(username="bad-groups").exists()

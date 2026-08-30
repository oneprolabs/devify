"""API tests for the expense configuration endpoints."""

import pytest

from expense.constants import DEFAULT_SCAN_SCHEDULE
from expense.models import ExpenseUserConfig
from expense.services.config_service import get_app_config


pytestmark = [pytest.mark.integration, pytest.mark.django_db]

CONFIG_URL = "/api/v1/apps/expense/config"
ADMIN_CONFIG_URL = "/api/v1/admin/apps/expense/config"
APPS_URL = "/api/v1/apps"


class TestUserConfigAPI:
    def test_requires_authentication(self, api_client):
        assert api_client.get(CONFIG_URL).status_code in (401, 403)

    def test_get_creates_a_disabled_config(self, api_client, user):
        api_client.force_authenticate(user=user)

        response = api_client.get(CONFIG_URL)

        assert response.status_code == 200
        data = response.data["data"]
        assert data["enabled"] is False
        assert ExpenseUserConfig.objects.filter(user=user).exists()

    def test_response_carries_the_price_and_balance(self, api_client, user):
        # The enable card must be able to state the price before the user
        # flips the switch, without a second request.
        api_client.force_authenticate(user=user)

        data = api_client.get(CONFIG_URL).data["data"]

        assert data["cost_credits_per_email"] == 1
        assert "credits_balance" in data

    def test_enabling_stamps_enabled_at(self, api_client, user):
        api_client.force_authenticate(user=user)

        response = api_client.patch(
            CONFIG_URL, {"enabled": True}, format="json"
        )
        data = response.data["data"]

        assert data["enabled"] is True
        assert data["enabled_at"] is not None

    def test_preferences_are_cleaned_and_deduplicated(self, api_client, user):
        api_client.force_authenticate(user=user)

        data = api_client.patch(
            CONFIG_URL,
            {"keyword_filters": ["发票", " 发票 ", "", "invoice"]},
            format="json",
        ).data["data"]

        assert data["keyword_filters"] == ["发票", "invoice"]

    def test_rejects_a_non_list_preference(self, api_client, user):
        api_client.force_authenticate(user=user)

        response = api_client.patch(
            CONFIG_URL, {"sender_allowlist": "not-a-list"}, format="json"
        )

        assert response.status_code == 400

    def test_users_cannot_see_each_other_config(
        self, api_client, user, other_user
    ):
        api_client.force_authenticate(user=user)
        api_client.patch(CONFIG_URL, {"home_city": "上海"}, format="json")

        api_client.force_authenticate(user=other_user)
        data = api_client.get(CONFIG_URL).data["data"]

        assert data["home_city"] == ""


class TestAdminConfigAPI:
    def test_regular_users_are_rejected(self, api_client, user):
        api_client.force_authenticate(user=user)

        assert api_client.get(ADMIN_CONFIG_URL).status_code == 403

    def test_get_returns_platform_defaults(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)

        data = api_client.get(ADMIN_CONFIG_URL).data["data"]

        assert data["scan_schedule"] == DEFAULT_SCAN_SCHEDULE
        assert data["is_active"] is True

    def test_updating_the_cron_syncs_beat_immediately(
        self, api_client, admin_user
    ):
        from django_celery_beat.models import PeriodicTask

        from expense.constants import SCAN_TASK_NAME

        api_client.force_authenticate(user=admin_user)
        payload = {
            "scan_schedule": "15 4 * * *",
            "max_pdf_pages": 5,
            "link_domain_allowlist": ["fapiao.example.com"],
            "max_download_bytes": 1024,
            "is_active": True,
        }

        response = api_client.put(ADMIN_CONFIG_URL, payload, format="json")

        assert response.status_code == 200
        assert response.data["data"]["schedule_sync"]["enabled"] is True
        crontab = PeriodicTask.objects.get(name=SCAN_TASK_NAME).crontab
        assert crontab.minute == "15"
        assert crontab.hour == "4"
        assert get_app_config().scan_schedule == "15 4 * * *"

    def test_rejects_a_malformed_cron(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)

        response = api_client.put(
            ADMIN_CONFIG_URL,
            {"scan_schedule": "not a cron", "is_active": True},
            format="json",
        )

        assert response.status_code == 400


class TestAppsAPI:
    def test_expense_appears_in_the_application_center(self, api_client, user):
        api_client.force_authenticate(user=user)

        keys = [app["key"] for app in api_client.get(APPS_URL).data["data"]]

        assert "expense" in keys
        assert "relay" in keys

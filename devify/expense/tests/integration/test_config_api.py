"""API tests for the expense configuration endpoints."""

import pytest

from expense.constants import DEFAULT_SCAN_SCHEDULE
from expense.models import ExpenseUserConfig
from expense.services.config_service import get_app_config
from threadline.models import EmailMailbox

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

    def test_disabling_clears_invoice_mode_from_the_users_mailboxes(
        self, api_client, user, other_user
    ):
        config = ExpenseUserConfig.objects.create(user=user, enabled=True)
        own_mailbox = EmailMailbox.objects.create(
            user=user,
            imap_host="imap.example.com",
            username="mine@example.com",
            password="secret",
            invoice_only=True,
        )
        other_mailbox = EmailMailbox.objects.create(
            user=other_user,
            imap_host="imap.example.com",
            username="other@example.com",
            password="secret",
            invoice_only=True,
        )
        api_client.force_authenticate(user=user)

        response = api_client.patch(
            CONFIG_URL, {"enabled": False}, format="json"
        )

        config.refresh_from_db()
        own_mailbox.refresh_from_db()
        other_mailbox.refresh_from_db()
        assert response.status_code == 200
        assert config.enabled is False
        assert own_mailbox.invoice_only is False
        assert other_mailbox.invoice_only is True

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


class TestUserConfigConcurrency:
    @pytest.mark.django_db(transaction=True)
    def test_preference_save_preserves_a_concurrent_enable(
        self, django_user_model
    ):
        from concurrent.futures import ThreadPoolExecutor
        from queue import Queue
        from threading import current_thread
        from unittest.mock import patch

        from django.db import close_old_connections, transaction
        from django.db.models.query import QuerySet
        from rest_framework.test import APIClient

        from expense.serializers import ExpenseUserConfigSerializer
        from expense.services.config_service import (
            get_user_config,
            set_user_enabled,
        )

        user = django_user_model.objects.create_user(
            "expense-config-race", password="x"
        )
        config = get_user_config(user)
        preference_stage = Queue()
        original_select_for_update = QuerySet.select_for_update
        original_save = ExpenseUserConfigSerializer.save

        def signal_config_lock(queryset, *args, **kwargs):
            if (
                current_thread().name.startswith("save-preferences")
                and queryset.model is ExpenseUserConfig
            ):
                preference_stage.put("config-lock")
            return original_select_for_update(queryset, *args, **kwargs)

        def signal_preference_save(serializer, *args, **kwargs):
            if current_thread().name.startswith("save-preferences"):
                preference_stage.put("preference-save")
            return original_save(serializer, *args, **kwargs)

        def save_preferences():
            close_old_connections()
            try:
                client = APIClient()
                client.force_authenticate(user=user)
                return client.patch(
                    CONFIG_URL,
                    {"home_city": "Shanghai"},
                    format="json",
                ).status_code
            finally:
                close_old_connections()

        pool = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="save-preferences"
        )
        try:
            with (
                patch.object(
                    QuerySet,
                    "select_for_update",
                    new=signal_config_lock,
                ),
                patch.object(
                    ExpenseUserConfigSerializer,
                    "save",
                    new=signal_preference_save,
                ),
            ):
                with transaction.atomic():
                    ExpenseUserConfig.objects.select_for_update().get(
                        pk=config.pk
                    )
                    future = pool.submit(save_preferences)
                    assert preference_stage.get(timeout=5) in {
                        "config-lock",
                        "preference-save",
                    }
                    set_user_enabled(config, True)

                assert future.result(timeout=5) == 200
        finally:
            pool.shutdown(wait=True)

        config.refresh_from_db()
        assert config.enabled is True
        assert config.home_city == "Shanghai"


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

    def test_saving_one_section_leaves_the_others_alone(
        self, api_client, admin_user
    ):
        # The admin page saves per section; a full replace would blank the
        # cron whenever someone only changed the models.
        api_client.force_authenticate(user=admin_user)
        api_client.put(
            ADMIN_CONFIG_URL,
            {"scan_schedule": "15 4 * * *", "max_pdf_pages": 5},
            format="json",
        )

        api_client.put(
            ADMIN_CONFIG_URL,
            {"llm_config_uuid": "33333333-3333-3333-3333-333333333333"},
            format="json",
        )

        config = get_app_config()
        assert config.scan_schedule == "15 4 * * *"
        assert config.max_pdf_pages == 5
        assert str(config.llm_config_uuid).startswith("33333333")

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

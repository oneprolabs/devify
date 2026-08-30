"""Integration tests for the periodic scan dispatcher."""

import pytest

from expense.services.config_service import (
    get_app_config,
    get_user_config,
    set_user_enabled,
)
from expense.tasks.scheduler import schedule_invoice_scan


pytestmark = [pytest.mark.integration, pytest.mark.django_db]


class TestScheduleInvoiceScan:
    def test_counts_only_enabled_users(self, user, other_user):
        set_user_enabled(get_user_config(user), True)
        get_user_config(other_user)

        result = schedule_invoice_scan()

        assert result["enabled_users"] == 1

    def test_skips_everything_when_the_app_is_inactive(self, user):
        set_user_enabled(get_user_config(user), True)
        config = get_app_config()
        config.is_active = False
        config.save(update_fields=["is_active"])

        result = schedule_invoice_scan()

        assert result["skipped_reason"] == "app_inactive"

    def test_m1_does_not_queue_any_work_yet(self, user):
        # Recognition and billing land in M2/M3; M1 must stay a no-op so
        # enabling the app cannot consume credits.
        set_user_enabled(get_user_config(user), True)

        assert schedule_invoice_scan()["dispatched"] == 0

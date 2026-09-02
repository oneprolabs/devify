"""Integration tests for the periodic scan dispatcher."""

import pytest

from expense.models import InvoiceScanRun
from expense.services.config_service import (
    get_app_config,
    get_user_config,
    set_user_enabled,
)
from expense.tasks.scheduler import schedule_invoice_scan


pytestmark = [pytest.mark.integration, pytest.mark.django_db]


class TestScheduleInvoiceScan:
    def test_dispatches_only_for_enabled_users(self, user, other_user):
        set_user_enabled(get_user_config(user), True)
        get_user_config(other_user)

        result = schedule_invoice_scan()

        assert result["dispatched"] == 1
        assert InvoiceScanRun.objects.filter(user=user).count() == 1
        assert InvoiceScanRun.objects.filter(user=other_user).count() == 0

    def test_runs_are_marked_as_scheduled(self, user):
        set_user_enabled(get_user_config(user), True)

        schedule_invoice_scan()

        run = InvoiceScanRun.objects.get(user=user)
        assert run.trigger == InvoiceScanRun.Trigger.SCHEDULED

    def test_skips_everything_when_the_app_is_inactive(self, user):
        set_user_enabled(get_user_config(user), True)
        config = get_app_config()
        config.is_active = False
        config.save(update_fields=["is_active"])

        result = schedule_invoice_scan()

        assert result["skipped_reason"] == "app_inactive"
        assert InvoiceScanRun.objects.count() == 0

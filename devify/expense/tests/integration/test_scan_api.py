"""API tests for the scan endpoints."""

from datetime import timedelta

import pytest
from django.utils import timezone

from expense.models import InvoiceScanRun
from expense.services.config_service import get_user_config, set_user_enabled
from threadline.models import EmailAttachment, EmailMessage


pytestmark = [pytest.mark.integration, pytest.mark.django_db]

SCAN_URL = "/api/v1/apps/expense/scan"
PREVIEW_URL = "/api/v1/apps/expense/scan/preview"
RUNS_URL = "/api/v1/apps/expense/scan-runs"


def seed_invoice_email(user, counter=[0]):
    counter[0] += 1
    email = EmailMessage.objects.create(
        user=user,
        message_id=f"email_api_{counter[0]:04d}",
        subject="您的发票",
        sender="billing@example.com",
        recipients="user@example.com",
        received_at=timezone.now() - timedelta(hours=1),
    )
    EmailAttachment.objects.create(
        user=user,
        email_message=email,
        filename="invoice.pdf",
        safe_filename="invoice.pdf",
        content_type="application/pdf",
        file_size=100_000,
        file_path="/tmp/invoice.pdf",
        content_md5="0" * 32,
    )
    return email


class TestScanPreviewAPI:
    def test_requires_authentication(self, api_client):
        assert api_client.post(PREVIEW_URL).status_code in (401, 403)

    def test_preview_reports_cost_before_committing(self, api_client, user):
        set_user_enabled(get_user_config(user), True)
        seed_invoice_email(user)
        api_client.force_authenticate(user=user)

        response = api_client.post(
            PREVIEW_URL, {"lookback_days": 30}, format="json"
        )

        data = response.data["data"]
        assert response.status_code == 200
        assert data["candidate_emails"] == 1
        assert data["estimated_credits"] == 1
        assert InvoiceScanRun.objects.count() == 0

    def test_rejects_both_scoping_options_at_once(self, api_client, user):
        api_client.force_authenticate(user=user)

        response = api_client.post(
            PREVIEW_URL,
            {"lookback_days": 7, "email_uuids": [str(user.id)]},
            format="json",
        )

        assert response.status_code == 400

    def test_rejects_an_out_of_range_lookback(self, api_client, user):
        api_client.force_authenticate(user=user)

        response = api_client.post(
            PREVIEW_URL, {"lookback_days": 4000}, format="json"
        )

        assert response.status_code == 400


class TestScanAPI:
    def test_scan_creates_a_run_and_returns_it(self, api_client, user):
        set_user_enabled(get_user_config(user), True)
        seed_invoice_email(user)
        api_client.force_authenticate(user=user)

        response = api_client.post(SCAN_URL, {}, format="json")

        assert response.status_code == 202
        assert InvoiceScanRun.objects.filter(user=user).count() == 1
        assert (
            response.data["data"]["trigger"]
            == InvoiceScanRun.Trigger.MANUAL
        )

    def test_scoped_scan_is_recorded_as_a_backfill(self, api_client, user):
        set_user_enabled(get_user_config(user), True)
        api_client.force_authenticate(user=user)

        response = api_client.post(
            SCAN_URL, {"lookback_days": 30}, format="json"
        )

        assert (
            response.data["data"]["trigger"] == InvoiceScanRun.Trigger.BACKFILL
        )


class TestScanRunAPI:
    def test_list_returns_only_own_runs(self, api_client, user, other_user):
        InvoiceScanRun.objects.create(user=user)
        InvoiceScanRun.objects.create(user=other_user)
        api_client.force_authenticate(user=user)

        response = api_client.get(RUNS_URL)

        assert len(response.data["data"]) == 1

    def test_detail_exposes_per_email_verdicts(self, api_client, user):
        run = InvoiceScanRun.objects.create(
            user=user, details={"summary": {}, "emails": []}
        )
        api_client.force_authenticate(user=user)

        response = api_client.get(f"{RUNS_URL}/{run.uuid}")

        assert response.status_code == 200
        assert "details" in response.data["data"]

    def test_another_users_run_is_not_found(
        self, api_client, user, other_user
    ):
        run = InvoiceScanRun.objects.create(user=other_user)
        api_client.force_authenticate(user=user)

        assert api_client.get(f"{RUNS_URL}/{run.uuid}").status_code == 404

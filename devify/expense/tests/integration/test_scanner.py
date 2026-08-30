"""Integration tests for scan scoping, previews and run records."""

from datetime import timedelta

import pytest
from django.utils import timezone

from expense.models import InvoiceScanRun
from expense.services.config_service import get_app_config, get_user_config
from expense.services.config_service import set_user_enabled
from expense.services.scanner import (
    execute_scan,
    preview_scan,
    resolve_since,
)
from threadline.models import EmailAttachment, EmailMessage


pytestmark = [pytest.mark.integration, pytest.mark.django_db]


def make_email(user, subject="您的发票", days_ago=0, body="", counter=[0]):
    counter[0] += 1
    return EmailMessage.objects.create(
        user=user,
        message_id=f"email_scan_{counter[0]:04d}",
        subject=subject,
        sender="billing@example.com",
        recipients="user@example.com",
        received_at=timezone.now() - timedelta(days=days_ago),
        text_content=body,
    )


def attach(user, email, filename="invoice.pdf", content_type="application/pdf",
           size=100_000):
    return EmailAttachment.objects.create(
        user=user,
        email_message=email,
        filename=filename,
        safe_filename=filename,
        content_type=content_type,
        file_size=size,
        file_path=f"/tmp/{filename}",
        content_md5="0" * 32,
    )


class TestResolveSince:
    def test_lookback_wins_over_the_watermark(self, user):
        config = set_user_enabled(get_user_config(user), True)
        since = resolve_since(config, lookback_days=7)
        assert since < config.enabled_at

    def test_watermark_is_the_later_of_enabled_and_last_scanned(self, user):
        config = set_user_enabled(get_user_config(user), True)
        config.last_scanned_at = config.enabled_at + timedelta(days=1)
        config.save(update_fields=["last_scanned_at"])

        assert resolve_since(config) == config.last_scanned_at

    def test_no_floor_when_the_app_was_never_enabled(self, user):
        assert resolve_since(get_user_config(user)) is None


class TestPreviewScan:
    def test_preview_counts_candidates_and_credits(self, user):
        set_user_enabled(get_user_config(user), True)
        email = make_email(user)
        attach(user, email)

        result = preview_scan(user, lookback_days=30)

        assert result["candidate_emails"] == 1
        assert result["estimated_credits"] == result["cost_credits_per_email"]

    def test_preview_writes_nothing(self, user):
        set_user_enabled(get_user_config(user), True)
        email = make_email(user)
        attach(user, email)

        preview_scan(user, lookback_days=30)

        assert InvoiceScanRun.objects.count() == 0

    def test_unrelated_email_is_not_a_candidate(self, user):
        set_user_enabled(get_user_config(user), True)
        email = make_email(user, subject="周会纪要")
        attach(user, email, filename="notes.pdf")

        result = preview_scan(user, lookback_days=30)

        assert result["candidate_emails"] == 0
        assert result["non_candidate_emails"] == 1

    def test_emails_outside_the_window_are_not_scanned(self, user):
        set_user_enabled(get_user_config(user), True)
        old = make_email(user, days_ago=60)
        attach(user, old)

        result = preview_scan(user, lookback_days=7)

        assert result["emails_scanned"] == 0

    def test_merged_children_are_skipped(self, user):
        set_user_enabled(get_user_config(user), True)
        parent = make_email(user)
        attach(user, parent)
        child = make_email(user)
        attach(user, child)
        child.merged_into = parent
        child.save(update_fields=["merged_into"])

        result = preview_scan(user, lookback_days=30)

        assert result["emails_scanned"] == 1

    def test_another_users_email_is_invisible(self, user, other_user):
        set_user_enabled(get_user_config(user), True)
        theirs = make_email(other_user)
        attach(other_user, theirs)

        result = preview_scan(user, lookback_days=30)

        assert result["emails_scanned"] == 0

    def test_pending_dependency_attachments_are_reported(self, user):
        set_user_enabled(get_user_config(user), True)
        email = make_email(user)
        attach(user, email)
        attach(
            user,
            email,
            filename="forwarded.eml",
            content_type="message/rfc822",
        )

        result = preview_scan(user, lookback_days=30)

        assert result["pending_dependency_attachments"] == 1

    def test_blocked_links_surface_for_the_user_to_allow(self, user):
        set_user_enabled(get_user_config(user), True)
        email = make_email(user, body="https://random.test/invoice.pdf")
        attach(user, email)

        result = preview_scan(user, lookback_days=30)

        assert len(result["blocked_links"]) == 1

    def test_targeted_uuids_ignore_the_window(self, user):
        set_user_enabled(get_user_config(user), True)
        old = make_email(user, days_ago=200)
        attach(user, old)

        result = preview_scan(user, email_uuids=[str(old.uuid)])

        assert result["candidate_emails"] == 1


class TestExecuteScan:
    def test_run_records_the_summary(self, user):
        set_user_enabled(get_user_config(user), True)
        email = make_email(user)
        attach(user, email)
        run = InvoiceScanRun.objects.create(user=user)

        execute_scan(run, lookback_days=30)
        run.refresh_from_db()

        assert run.status == InvoiceScanRun.Status.COMPLETED
        assert run.emails_scanned == 1
        assert run.candidate_emails == 1
        assert run.details["summary"]["estimated_credits"] == 1

    def test_undecodable_attachment_costs_nothing(self, user):
        # The fixture points at a path that does not exist, so decoding
        # fails before any model is called. The user must not be billed.
        set_user_enabled(get_user_config(user), True)
        email = make_email(user)
        attach(user, email)
        run = InvoiceScanRun.objects.create(user=user)

        execute_scan(run, lookback_days=30)
        run.refresh_from_db()

        assert run.credits_consumed == 0
        assert run.invoices_created == 0
        assert run.failed == 1

    def test_watermark_advances_after_a_full_scan(self, user):
        config = set_user_enabled(get_user_config(user), True)
        email = make_email(user)
        attach(user, email)
        run = InvoiceScanRun.objects.create(user=user)

        execute_scan(run, lookback_days=30)
        config.refresh_from_db()

        assert config.last_scanned_at is not None

    def test_targeted_scan_leaves_the_watermark_alone(self, user):
        # Recognizing two named emails says nothing about the rest of the
        # mailbox, so it must not claim everything up to now was handled.
        config = set_user_enabled(get_user_config(user), True)
        email = make_email(user)
        attach(user, email)
        run = InvoiceScanRun.objects.create(user=user)

        execute_scan(run, email_uuids=[str(email.uuid)])
        config.refresh_from_db()

        assert config.last_scanned_at is None

    def test_watermark_never_moves_backwards(self, user):
        config = set_user_enabled(get_user_config(user), True)
        future = timezone.now() + timedelta(days=1)
        config.last_scanned_at = future
        config.save(update_fields=["last_scanned_at"])
        run = InvoiceScanRun.objects.create(user=user)

        execute_scan(run, lookback_days=30)
        config.refresh_from_db()

        assert config.last_scanned_at == future

    def test_candidate_details_name_the_source(self, user):
        set_user_enabled(get_user_config(user), True)
        email = make_email(user)
        attach(user, email, filename="fapiao-202608.pdf")
        run = InvoiceScanRun.objects.create(user=user)

        execute_scan(run, lookback_days=30)
        run.refresh_from_db()

        source = run.details["emails"][0]["sources"][0]
        assert source["label"] == "fapiao-202608.pdf"
        assert source["kind"] == "attachment"

    def test_app_config_size_cap_is_honored(self, user):
        set_user_enabled(get_user_config(user), True)
        config = get_app_config()
        config.max_download_bytes = 1024
        config.save(update_fields=["max_download_bytes"])
        email = make_email(user)
        attach(user, email, size=100_000)
        run = InvoiceScanRun.objects.create(user=user)

        execute_scan(run, lookback_days=30)
        run.refresh_from_db()

        assert run.candidate_emails == 0

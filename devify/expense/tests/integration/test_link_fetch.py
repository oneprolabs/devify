"""Integration tests for the download path and the release flow."""

from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from django.utils import timezone

from expense.models import InvoiceSourceFile
from expense.services.config_service import get_app_config
from expense.services.link_fetcher import fetch_link
from threadline.models import EmailMessage


pytestmark = [pytest.mark.integration, pytest.mark.django_db]

ALLOWED = ["fapiao.example.com"]
URL = "https://fapiao.example.com/d/1"
RESOLVE_PATH = "expense.services.link_fetcher.host_addresses"
LINKS_URL = "/api/v1/apps/expense/links"

PDF_BODY = b"%PDF-1.4 minimal invoice body"


def make_email(user, counter=[0]):
    counter[0] += 1
    return EmailMessage.objects.create(
        user=user,
        message_id=f"email_link_{counter[0]:04d}",
        subject="您的发票",
        sender="billing@example.com",
        recipients="user@example.com",
        received_at=timezone.now() - timedelta(hours=1),
    )


def fake_response(
    body=PDF_BODY, content_type="application/pdf", status_code=200,
    headers=None, redirect_to=None,
):
    response = MagicMock()
    response.status_code = status_code
    response.is_redirect = bool(redirect_to)
    response.is_permanent_redirect = False
    response.headers = {"Content-Type": content_type}
    if headers:
        response.headers.update(headers)
    if redirect_to:
        response.headers["Location"] = redirect_to
    response.iter_content = lambda size: [body]
    response.__enter__ = lambda self_: self_
    response.__exit__ = lambda *args: False
    response.close = lambda: None
    return response


def session_returning(*responses):
    session = MagicMock()
    session.get = MagicMock(side_effect=list(responses))
    return session


class TestFetchLink:
    def test_a_clean_pdf_is_stored(self, user, tmp_path, settings):
        settings.EMAIL_ATTACHMENT_DIR = str(tmp_path)
        email = make_email(user)

        with patch(RESOLVE_PATH, return_value=["8.8.8.8"]):
            outcome = fetch_link(
                URL,
                email,
                ALLOWED,
                max_bytes=1_000_000,
                session=session_returning(fake_response()),
            )

        assert outcome.ok
        assert outcome.content_type == "application/pdf"
        assert outcome.content_md5
        assert open(outcome.file_path, "rb").read() == PDF_BODY

    def test_an_unlisted_domain_is_never_requested(self, user):
        email = make_email(user)
        session = session_returning(fake_response())

        with patch(RESOLVE_PATH, return_value=["8.8.8.8"]):
            outcome = fetch_link(
                "https://evil.test/x", email, ALLOWED, 1_000_000,
                session=session,
            )

        assert outcome.status == InvoiceSourceFile.FetchStatus.BLOCKED_DOMAIN
        session.get.assert_not_called()

    def test_a_redirect_into_the_private_network_is_stopped(self, user):
        # The first hop is legitimate; the redirect is the attack.
        email = make_email(user)
        responses = [
            fake_response(redirect_to="https://fapiao.example.com/internal"),
            fake_response(),
        ]

        hops = [["8.8.8.8"], ["169.254.169.254"]]
        with patch(RESOLVE_PATH, side_effect=hops):
            outcome = fetch_link(
                URL, email, ALLOWED, 1_000_000,
                session=session_returning(*responses),
            )

        assert outcome.status == InvoiceSourceFile.FetchStatus.BLOCKED_IP

    def test_a_redirect_off_the_allowlist_is_stopped(self, user):
        email = make_email(user)
        responses = [
            fake_response(redirect_to="https://evil.test/payload"),
            fake_response(),
        ]

        with patch(RESOLVE_PATH, return_value=["8.8.8.8"]):
            outcome = fetch_link(
                URL, email, ALLOWED, 1_000_000,
                session=session_returning(*responses),
            )

        assert outcome.status == InvoiceSourceFile.FetchStatus.BLOCKED_DOMAIN

    def test_a_redirect_chain_is_capped(self, user):
        email = make_email(user)
        responses = [
            fake_response(redirect_to=URL) for _ in range(6)
        ]

        with patch(RESOLVE_PATH, return_value=["8.8.8.8"]):
            outcome = fetch_link(
                URL, email, ALLOWED, 1_000_000,
                session=session_returning(*responses),
            )

        assert outcome.status == InvoiceSourceFile.FetchStatus.FAILED
        assert "redirect" in outcome.error.lower()

    def test_an_oversized_declared_body_is_refused(self, user):
        email = make_email(user)
        response = fake_response(headers={"Content-Length": "99999999"})

        with patch(RESOLVE_PATH, return_value=["8.8.8.8"]):
            outcome = fetch_link(
                URL, email, ALLOWED, 1000,
                session=session_returning(response),
            )

        assert outcome.status == InvoiceSourceFile.FetchStatus.TOO_LARGE

    def test_a_body_that_lies_about_its_size_is_cut_off(self, user):
        # Content-Length said nothing; the stream is capped as it arrives.
        email = make_email(user)
        response = fake_response(body=b"%PDF" + b"x" * 5000)

        with patch(RESOLVE_PATH, return_value=["8.8.8.8"]):
            outcome = fetch_link(
                URL, email, ALLOWED, 1000,
                session=session_returning(response),
            )

        assert outcome.status == InvoiceSourceFile.FetchStatus.TOO_LARGE

    def test_a_login_page_is_reported_as_needing_auth(self, user):
        email = make_email(user)
        response = fake_response(
            body=b"<html>sign in</html>", content_type="text/html"
        )

        with patch(RESOLVE_PATH, return_value=["8.8.8.8"]):
            outcome = fetch_link(
                URL, email, ALLOWED, 1_000_000,
                session=session_returning(response),
            )

        assert outcome.status == InvoiceSourceFile.FetchStatus.REQUIRES_AUTH

    def test_a_file_lying_about_its_type_is_refused(self, user, tmp_path,
                                                    settings):
        # Header claims PDF, bytes are a shell script.
        settings.EMAIL_ATTACHMENT_DIR = str(tmp_path)
        email = make_email(user)
        response = fake_response(body=b"#!/bin/sh\nrm -rf /")

        with patch(RESOLVE_PATH, return_value=["8.8.8.8"]):
            outcome = fetch_link(
                URL, email, ALLOWED, 1_000_000,
                session=session_returning(response),
            )

        assert outcome.status == InvoiceSourceFile.FetchStatus.BAD_TYPE

    def test_an_unexpected_declared_type_is_refused(self, user):
        email = make_email(user)
        response = fake_response(content_type="application/x-msdownload")

        with patch(RESOLVE_PATH, return_value=["8.8.8.8"]):
            outcome = fetch_link(
                URL, email, ALLOWED, 1_000_000,
                session=session_returning(response),
            )

        assert outcome.status == InvoiceSourceFile.FetchStatus.BAD_TYPE

    def test_an_error_response_is_recorded(self, user):
        email = make_email(user)
        response = fake_response(status_code=404)

        with patch(RESOLVE_PATH, return_value=["8.8.8.8"]):
            outcome = fetch_link(
                URL, email, ALLOWED, 1_000_000,
                session=session_returning(response),
            )

        assert outcome.status == InvoiceSourceFile.FetchStatus.FAILED
        assert "404" in outcome.error


class TestLinkAPI:
    def test_blocked_links_are_listed(self, api_client, user):
        email = make_email(user)
        InvoiceSourceFile.objects.create(
            user=user,
            email_message=email,
            source_url="https://evil.test/x",
            fetch_status=InvoiceSourceFile.FetchStatus.BLOCKED_DOMAIN,
        )
        api_client.force_authenticate(user=user)

        response = api_client.get(f"{LINKS_URL}?status=blocked_domain")

        assert response.status_code == 200
        assert len(response.data["data"]) == 1

    def test_releasing_a_link_marks_it_and_starts_a_rescan(
        self, api_client, user
    ):
        email = make_email(user)
        record = InvoiceSourceFile.objects.create(
            user=user,
            email_message=email,
            source_url="https://evil.test/x",
            fetch_status=InvoiceSourceFile.FetchStatus.BLOCKED_DOMAIN,
        )
        api_client.force_authenticate(user=user)

        response = api_client.post(f"{LINKS_URL}/{record.uuid}/allow")

        record.refresh_from_db()
        assert response.status_code == 202
        assert record.user_allowed is True
        assert response.data["data"]["run_uuid"]

    def test_another_users_link_cannot_be_released(
        self, api_client, user, other_user
    ):
        email = make_email(other_user)
        record = InvoiceSourceFile.objects.create(
            user=other_user,
            email_message=email,
            source_url="https://evil.test/x",
            fetch_status=InvoiceSourceFile.FetchStatus.BLOCKED_DOMAIN,
        )
        api_client.force_authenticate(user=user)

        response = api_client.post(f"{LINKS_URL}/{record.uuid}/allow")

        record.refresh_from_db()
        assert response.status_code == 404
        assert record.user_allowed is False

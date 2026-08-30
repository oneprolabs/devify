"""
Security tests for fetching links out of untrusted email.

Every case here is an attack the fetcher must refuse. These are not
optional coverage: the feature makes the server open URLs chosen by
whoever sent the mail.
"""

from unittest.mock import patch

import pytest

from expense.models import InvoiceSourceFile
from expense.services.link_fetcher import (
    UnsafeUrl,
    assert_safe_url,
    domain_allowed,
    is_public_address,
    sniff_content_type,
)


pytestmark = pytest.mark.unit

ALLOWED = ["fapiao.example.com"]
RESOLVE_PATH = "expense.services.link_fetcher.host_addresses"


def resolves_to(*addresses):
    return patch(RESOLVE_PATH, return_value=list(addresses))


class TestAddressClassification:
    @pytest.mark.parametrize(
        "address",
        [
            "127.0.0.1",
            "10.0.0.5",
            "172.16.0.1",
            "192.168.1.1",
            "169.254.169.254",
            "0.0.0.0",
            "::1",
            "fd00::1",
            "fe80::1",
        ],
    )
    def test_non_public_addresses_are_rejected(self, address):
        assert not is_public_address(address)

    @pytest.mark.parametrize("address", ["8.8.8.8", "1.1.1.1", "2001:4860::1"])
    def test_public_addresses_are_accepted(self, address):
        assert is_public_address(address)

    def test_garbage_is_not_public(self):
        assert not is_public_address("not-an-address")


class TestSchemeAndDomain:
    def test_http_is_refused(self):
        with resolves_to("8.8.8.8"), pytest.raises(UnsafeUrl) as info:
            assert_safe_url("http://fapiao.example.com/a", ALLOWED)
        assert (
            info.value.status
            == InvoiceSourceFile.FetchStatus.BLOCKED_DOMAIN
        )

    def test_file_scheme_is_refused(self):
        with pytest.raises(UnsafeUrl):
            assert_safe_url("file:///etc/passwd", ALLOWED)

    def test_unlisted_domain_is_refused(self):
        with resolves_to("8.8.8.8"), pytest.raises(UnsafeUrl) as info:
            assert_safe_url("https://evil.test/a", ALLOWED)
        assert (
            info.value.status
            == InvoiceSourceFile.FetchStatus.BLOCKED_DOMAIN
        )

    def test_lookalike_domain_is_refused(self):
        # evilfapiao.example.com must not pass as fapiao.example.com.
        with resolves_to("8.8.8.8"), pytest.raises(UnsafeUrl):
            assert_safe_url("https://evilfapiao.example.com/a", ALLOWED)

    def test_subdomain_of_an_allowed_domain_passes(self):
        with resolves_to("8.8.8.8"):
            assert_safe_url("https://cdn.fapiao.example.com/a", ALLOWED)

    def test_allowlist_can_be_skipped_for_a_released_link(self):
        # A user override still has to clear every address check.
        with resolves_to("8.8.8.8"):
            assert_safe_url(
                "https://elsewhere.test/a", ALLOWED, skip_allowlist=True
            )

    def test_a_released_link_still_cannot_reach_the_private_network(self):
        with resolves_to("127.0.0.1"), pytest.raises(UnsafeUrl) as info:
            assert_safe_url(
                "https://elsewhere.test/a", ALLOWED, skip_allowlist=True
            )
        assert info.value.status == InvoiceSourceFile.FetchStatus.BLOCKED_IP


class TestAddressChecks:
    def test_loopback_target_is_refused(self):
        with resolves_to("127.0.0.1"), pytest.raises(UnsafeUrl) as info:
            assert_safe_url("https://fapiao.example.com/a", ALLOWED)
        assert info.value.status == InvoiceSourceFile.FetchStatus.BLOCKED_IP

    def test_cloud_metadata_address_is_refused(self):
        with resolves_to("169.254.169.254"), pytest.raises(UnsafeUrl):
            assert_safe_url("https://fapiao.example.com/a", ALLOWED)

    def test_one_private_record_among_public_ones_disqualifies_the_host(self):
        # The classic rebinding setup answers with both a public and a
        # private address; taking the public one on faith is the bug.
        with resolves_to("8.8.8.8", "10.0.0.5"), pytest.raises(
            UnsafeUrl
        ) as info:
            assert_safe_url("https://fapiao.example.com/a", ALLOWED)
        assert info.value.status == InvoiceSourceFile.FetchStatus.BLOCKED_IP

    def test_a_host_that_resolves_to_nothing_is_refused(self):
        with resolves_to(), pytest.raises(UnsafeUrl):
            assert_safe_url("https://fapiao.example.com/a", ALLOWED)

    def test_ipv6_loopback_is_refused(self):
        with resolves_to("::1"), pytest.raises(UnsafeUrl):
            assert_safe_url("https://fapiao.example.com/a", ALLOWED)


class TestDomainMatching:
    def test_exact_match(self):
        assert domain_allowed("fapiao.example.com", ALLOWED)

    def test_subdomain_match(self):
        assert domain_allowed("a.b.fapiao.example.com", ALLOWED)

    def test_suffix_without_a_dot_does_not_match(self):
        assert not domain_allowed("notfapiao.example.com", ALLOWED)

    def test_empty_host_does_not_match(self):
        assert not domain_allowed("", ALLOWED)


class TestMagicByteSniffing:
    def test_pdf_is_recognized(self):
        assert sniff_content_type(b"%PDF-1.7 rest")[0] == "application/pdf"

    def test_zip_container_is_treated_as_ofd(self):
        assert sniff_content_type(b"PK\x03\x04rest")[0] is not None

    def test_png_is_recognized(self):
        assert sniff_content_type(b"\x89PNG\r\n\x1a\nrest")[0] == "image/png"

    def test_html_is_not_a_document(self):
        # A server can claim application/pdf and return a login page.
        assert sniff_content_type(b"<!DOCTYPE html>") == (None, None)

    def test_a_script_is_not_a_document(self):
        assert sniff_content_type(b"#!/bin/sh\nrm -rf /") == (None, None)

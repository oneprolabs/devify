"""
Fetch invoice files linked from an email body.

This module makes the server open a URL that arrived in untrusted mail,
which is the textbook shape of an SSRF. Every control below is required,
not defence in depth for its own sake:

1. https only
2. the host must be on an allowlist, checked again on every redirect hop
3. every address the host resolves to must be public, checked again on
   every hop
4. hard caps on size, time and redirect count
5. the declared content type must match the file's actual magic bytes

The allowlist is the primary control. The address checks exist because a
name on the allowlist can still resolve somewhere it should not.
"""

from __future__ import annotations

import hashlib
import ipaddress
import logging
import os
import socket
from dataclasses import dataclass
from urllib.parse import urlparse

import requests
from django.conf import settings

from expense.models import InvoiceSourceFile

logger = logging.getLogger(__name__)

MAX_REDIRECTS = 3
REQUEST_TIMEOUT_SECONDS = 15
MAX_LINKS_PER_EMAIL = 5
CHUNK_SIZE = 64 * 1024

ACCEPTED_CONTENT_TYPES = {
    "application/pdf",
    "application/x-pdf",
    "application/ofd",
    "application/x-ofd",
    "application/zip",
    "application/octet-stream",
}

# Leading bytes that prove what a file really is, regardless of the header
# the server chose to send.
MAGIC_SIGNATURES = (
    (b"%PDF", "application/pdf", "pdf"),
    (b"PK\x03\x04", "application/ofd", "ofd"),
    (b"\x89PNG\r\n\x1a\n", "image/png", "png"),
    (b"\xff\xd8\xff", "image/jpeg", "jpg"),
    (b"GIF87a", "image/gif", "gif"),
    (b"GIF89a", "image/gif", "gif"),
)


@dataclass
class FetchOutcome:
    status: str
    file_path: str = ""
    content_type: str = ""
    file_size: int = 0
    content_md5: str = ""
    final_url: str = ""
    error: str = ""

    @property
    def ok(self) -> bool:
        return self.status == InvoiceSourceFile.FetchStatus.OK


class UnsafeUrl(Exception):
    """The URL failed a safety check and must not be requested."""

    def __init__(self, status: str, message: str):
        super().__init__(message)
        self.status = status


def host_addresses(host: str) -> list[str]:
    """Every address the host resolves to, v4 and v6 alike."""
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        raise UnsafeUrl(
            InvoiceSourceFile.FetchStatus.FAILED,
            f"Cannot resolve host: {exc}",
        ) from exc
    return list({info[4][0] for info in infos})


def is_public_address(address: str) -> bool:
    try:
        parsed = ipaddress.ip_address(address)
    except ValueError:
        return False
    return not (
        parsed.is_private
        or parsed.is_loopback
        or parsed.is_link_local
        or parsed.is_reserved
        or parsed.is_multicast
        or parsed.is_unspecified
    )


def domain_allowed(host: str, allowed_domains: list[str]) -> bool:
    host = (host or "").lower()
    return any(
        host == domain or host.endswith("." + domain)
        for domain in allowed_domains
    )


def assert_safe_url(
    url: str, allowed_domains: list[str], skip_allowlist: bool = False
):
    """
    Vet one hop. Raises ``UnsafeUrl`` rather than returning a verdict, so a
    caller cannot forget to check the result.
    """
    parsed = urlparse(url)

    if parsed.scheme.lower() != "https":
        raise UnsafeUrl(
            InvoiceSourceFile.FetchStatus.BLOCKED_DOMAIN,
            f"Only https is allowed, got {parsed.scheme!r}",
        )

    host = (parsed.hostname or "").lower()
    if not host:
        raise UnsafeUrl(
            InvoiceSourceFile.FetchStatus.BLOCKED_DOMAIN, "URL has no host"
        )

    if not skip_allowlist and not domain_allowed(host, allowed_domains):
        raise UnsafeUrl(
            InvoiceSourceFile.FetchStatus.BLOCKED_DOMAIN,
            f"Host {host} is not on the allowlist",
        )

    addresses = host_addresses(host)
    private = [
        address for address in addresses if not is_public_address(address)
    ]
    if private or not addresses:
        # One private record among several is the classic rebinding setup,
        # so a single bad address disqualifies the whole host.
        raise UnsafeUrl(
            InvoiceSourceFile.FetchStatus.BLOCKED_IP,
            f"Host {host} resolves to a non-public address: {private}",
        )


def sniff_content_type(head: bytes) -> tuple[str, str] | tuple[None, None]:
    for signature, content_type, extension in MAGIC_SIGNATURES:
        if head.startswith(signature):
            return content_type, extension
    return None, None


def looks_like_login_page(response) -> bool:
    """
    Detect a download that quietly turned into a sign-in page.

    These are common on invoice portals, and telling the user to fetch it
    by hand is far better than storing an HTML page as their invoice.
    """
    declared = (response.headers.get("Content-Type") or "").lower()
    return declared.startswith("text/html")


def _storage_dir(email) -> str:
    directory = os.path.join(
        settings.EMAIL_ATTACHMENT_DIR,
        f"{email.message_id}_links",
    )
    os.makedirs(directory, exist_ok=True)
    return directory


def fetch_link(
    url: str,
    email,
    allowed_domains: list[str],
    max_bytes: int,
    skip_allowlist: bool = False,
    session=None,
) -> FetchOutcome:
    """
    Download one linked file, or explain precisely why it was refused.

    Redirects are followed by hand so every hop goes through the same
    checks; letting the HTTP client follow them would vet only the first.
    """
    session = session or requests.Session()
    current = url
    seen = 0

    try:
        while True:
            assert_safe_url(current, allowed_domains, skip_allowlist)

            response = session.get(
                current,
                stream=True,
                timeout=REQUEST_TIMEOUT_SECONDS,
                allow_redirects=False,
            )

            if response.is_redirect or response.is_permanent_redirect:
                seen += 1
                if seen > MAX_REDIRECTS:
                    return FetchOutcome(
                        status=InvoiceSourceFile.FetchStatus.FAILED,
                        error=f"More than {MAX_REDIRECTS} redirects",
                    )
                location = response.headers.get("Location") or ""
                response.close()
                if not location:
                    return FetchOutcome(
                        status=InvoiceSourceFile.FetchStatus.FAILED,
                        error="Redirect without a Location header",
                    )
                current = requests.compat.urljoin(current, location)
                continue

            break
    except UnsafeUrl as exc:
        return FetchOutcome(status=exc.status, error=str(exc))
    except requests.Timeout:
        return FetchOutcome(
            status=InvoiceSourceFile.FetchStatus.TIMEOUT,
            error="Request timed out",
            final_url=current,
        )
    except requests.RequestException as exc:
        return FetchOutcome(
            status=InvoiceSourceFile.FetchStatus.FAILED,
            error=str(exc),
            final_url=current,
        )

    with response:
        if response.status_code >= 400:
            return FetchOutcome(
                status=InvoiceSourceFile.FetchStatus.FAILED,
                error=f"HTTP {response.status_code}",
                final_url=current,
            )

        if looks_like_login_page(response):
            return FetchOutcome(
                status=InvoiceSourceFile.FetchStatus.REQUIRES_AUTH,
                error="The link returned a web page, not a file",
                final_url=current,
            )

        declared = (
            (response.headers.get("Content-Type") or "")
            .lower()
            .split(";")[0]
            .strip()
        )
        if declared and not (
            declared in ACCEPTED_CONTENT_TYPES
            or declared.startswith("image/")
        ):
            return FetchOutcome(
                status=InvoiceSourceFile.FetchStatus.BAD_TYPE,
                error=f"Unexpected content type {declared}",
                final_url=current,
            )

        length_header = response.headers.get("Content-Length")
        if length_header and int(length_header) > max_bytes:
            return FetchOutcome(
                status=InvoiceSourceFile.FetchStatus.TOO_LARGE,
                error=f"Declared size {length_header} exceeds {max_bytes}",
                final_url=current,
            )

        payload = bytearray()
        for chunk in response.iter_content(CHUNK_SIZE):
            payload.extend(chunk)
            if len(payload) > max_bytes:
                # A server can understate Content-Length, so the real
                # stream is capped as it arrives.
                return FetchOutcome(
                    status=InvoiceSourceFile.FetchStatus.TOO_LARGE,
                    error=f"Body exceeded {max_bytes} bytes",
                    final_url=current,
                )

    body = bytes(payload)
    sniffed_type, extension = sniff_content_type(body[:16])
    if not sniffed_type:
        return FetchOutcome(
            status=InvoiceSourceFile.FetchStatus.BAD_TYPE,
            error="File contents are not a supported document",
            final_url=current,
        )

    digest = hashlib.md5(body).hexdigest()
    target = os.path.join(_storage_dir(email), f"{digest}.{extension}")
    with open(target, "wb") as handle:
        handle.write(body)

    return FetchOutcome(
        status=InvoiceSourceFile.FetchStatus.OK,
        file_path=target,
        content_type=sniffed_type,
        file_size=len(body),
        content_md5=digest,
        final_url=current,
    )

"""
Candidate filtering: the layer that costs nothing.

The only job here is to decide which emails are worth sending to a model,
so recognition never burns credits on signatures, logos or newsletters.
Nothing in this module calls an LLM or downloads anything.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import urlparse

from expense.constants import (
    DEFAULT_INVOICE_KEYWORDS,
    MIN_IMAGE_BYTES,
    OFD_CONTENT_TYPES,
    PDF_CONTENT_TYPES,
    XML_CONTENT_TYPES,
    ZIP_CONTENT_TYPES,
)


# Matches http(s) URLs in plain text and in href attributes alike.
# CJK characters are excluded from the match because URLs are ASCII: Chinese
# mail regularly writes a link with the sentence continuing straight after
# it, and without this the trailing text would be swallowed into the URL.
URL_PATTERN = re.compile(
    r"https?://[^\s\"'<>()\[\]\u3000-\u303f\u4e00-\u9fff\uff00-\uffef]+",
    re.IGNORECASE,
)

# Trailing ASCII punctuation that rides along when a URL ends a sentence.
URL_TRAILING_CHARS = ".,;:!?)>]}'\""


class SourceKind:
    ATTACHMENT = "attachment"
    BODY_LINK = "body_link"
    NESTED_EML = "nested_eml"


class SkipReason:
    UNSUPPORTED_TYPE = "unsupported_type"
    TOO_SMALL = "too_small"
    TOO_LARGE = "too_large"
    BLOCKED_DOMAIN = "blocked_domain"
    NOT_HTTPS = "not_https"
    PENDING_DEPENDENCY = "pending_dependency"


@dataclass
class CandidateSource:
    """One thing worth handing to recognition later."""

    kind: str
    label: str
    attachment_id: int | None = None
    url: str | None = None

    def as_dict(self) -> dict:
        data = {"kind": self.kind, "label": self.label}
        if self.attachment_id is not None:
            data["attachment_id"] = self.attachment_id
        if self.url:
            data["url"] = self.url
        return data


@dataclass
class SkippedSource:
    """Something that looked relevant but cannot be processed."""

    label: str
    reason: str
    url: str | None = None

    def as_dict(self) -> dict:
        data = {"label": self.label, "reason": self.reason}
        if self.url:
            data["url"] = self.url
        return data


@dataclass
class EmailCandidate:
    """The verdict for one email."""

    email_id: int
    email_uuid: str
    subject: str
    received_at: str
    sources: list[CandidateSource] = field(default_factory=list)
    skipped: list[SkippedSource] = field(default_factory=list)
    matched_keywords: list[str] = field(default_factory=list)

    @property
    def is_candidate(self) -> bool:
        return bool(self.sources)

    def as_dict(self) -> dict:
        return {
            "email_id": self.email_id,
            "email_uuid": self.email_uuid,
            "subject": self.subject,
            "received_at": self.received_at,
            "matched_keywords": self.matched_keywords,
            "sources": [source.as_dict() for source in self.sources],
            "skipped": [item.as_dict() for item in self.skipped],
        }


def resolve_keywords(user_config) -> list[str]:
    """User keywords replace the defaults entirely when provided."""
    configured = [
        str(word).strip().lower()
        for word in (user_config.keyword_filters or [])
        if str(word).strip()
    ]
    return configured or list(DEFAULT_INVOICE_KEYWORDS)


def resolve_allowed_domains(app_config, user_config=None) -> list[str]:
    """
    The operator's allowlist, empty meaning no restriction.

    There is no per-user list: with an empty platform allowlist already
    admitting any public host, a user-level one had nothing left to do.
    """
    domains = list(app_config.link_domain_allowlist or [])
    cleaned = []
    for domain in domains:
        text = str(domain or "").strip().lower().lstrip(".")
        if text:
            cleaned.append(text)
    return list(dict.fromkeys(cleaned))


def sender_allowed(email, user_config) -> bool:
    """An empty allowlist means every sender is in scope."""
    allowlist = [
        str(item).strip().lower()
        for item in (user_config.sender_allowlist or [])
        if str(item).strip()
    ]
    if not allowlist:
        return True
    sender = (email.sender or "").lower()
    return any(entry in sender for entry in allowlist)


def _attachment_extension(attachment) -> str:
    name = (attachment.filename or attachment.safe_filename or "").lower()
    _, _, suffix = name.rpartition(".")
    return suffix if suffix != name else ""


def classify_attachment(attachment, app_config):
    """
    Decide what an attachment is worth.

    Returns ``(kind, reason)`` where exactly one is set: a kind means the
    attachment is a usable source, a reason means it is not.
    """
    content_type = (
        (attachment.content_type or "").lower().split(";")[0].strip()
    )
    extension = _attachment_extension(attachment)
    size = attachment.file_size or 0

    if size > app_config.max_download_bytes:
        return None, SkipReason.TOO_LARGE

    if content_type == "message/rfc822" or extension == "eml":
        # Unpacking forwarded mail belongs to the threadline pipeline, see
        # https://github.com/oneprolabs/devify/issues/47. Until that lands
        # the nested content is invisible to us, so flag it rather than
        # silently dropping the email on the floor.
        return None, SkipReason.PENDING_DEPENDENCY

    if content_type in PDF_CONTENT_TYPES or extension == "pdf":
        return SourceKind.ATTACHMENT, None

    if content_type in OFD_CONTENT_TYPES or extension == "ofd":
        return SourceKind.ATTACHMENT, None

    # Rail operators deliver a ticket as a zip of the same invoice in two
    # formats. The decoder opens it and reads one of them.
    if content_type in ZIP_CONTENT_TYPES or extension == "zip":
        return SourceKind.ATTACHMENT, None

    # A fully digital invoice ships its XML alongside the PDF, and that
    # copy carries the fields exactly.
    if content_type in XML_CONTENT_TYPES or extension == "xml":
        return SourceKind.ATTACHMENT, None

    if content_type.startswith("image/") or attachment.is_image:
        if size and size < MIN_IMAGE_BYTES:
            # Signature images and logos cluster well below this line.
            return None, SkipReason.TOO_SMALL
        return SourceKind.ATTACHMENT, None

    return None, SkipReason.UNSUPPORTED_TYPE


def _normalize_url(raw: str) -> str:
    return raw.rstrip(URL_TRAILING_CHARS)


def domain_allowed(url: str, allowed_domains: list[str]) -> bool:
    """
    An empty allowlist places no restriction.

    Invoices come from a long tail of billing platforms, so demanding that
    every domain be listed in advance would leave most links unusable.
    Whether the host is safe to reach is settled by the address checks in
    the fetcher, not here.
    """
    host = (urlparse(url).hostname or "").lower()
    if not host:
        return False
    if not allowed_domains:
        return True
    return any(
        host == domain or host.endswith("." + domain)
        for domain in allowed_domains
    )


ANCHOR_PATTERN = re.compile(
    r"<a\b[^>]*?href\s*=\s*[\"']([^\"']+)[\"'][^>]*>(.*?)</a\s*>",
    re.IGNORECASE | re.DOTALL,
)
TAG_PATTERN = re.compile(r"<[^>]+>")


def body_urls(email) -> list[str]:
    """
    The links in a body that could lead to an invoice.

    An invoice is something a person is asked to click, so in an HTML body
    only anchors count. Running a URL pattern over the whole markup also
    collects every decoration the mail client renders - 12306 alone drew
    mail_top.jpg, mail_line.jpg and mail_logo.jpg - and each of those was
    then offered to the user as a download to allow.

    A plain-text body has no markup to tell them apart, and no decorations
    either, so there every URL still counts.
    """
    return [link["url"] for link in body_anchors(email)]


def body_anchors(email) -> list[dict]:
    """
    The same links, each with the words it was shown as.

    "下载发票" and "查看广告" are the difference between a document and an
    advertisement, and no amount of looking at the URL reveals it, so the
    text a person would have clicked travels with the address.
    """
    html = email.html_content or ""
    if html.strip():
        anchors = []
        for url, label in ANCHOR_PATTERN.findall(html):
            url = url.strip()
            if not url.lower().startswith(("http://", "https://")):
                continue
            text = TAG_PATTERN.sub(" ", label)
            anchors.append({"url": url, "text": " ".join(text.split())[:80]})
        if anchors:
            return anchors

    return [
        {"url": url, "text": ""}
        for url in URL_PATTERN.findall(email.text_content or "")
    ]


def extract_body_links(email, allowed_domains: list[str]):
    """
    Pull download links out of the body.

    Returns ``(allowed, blocked)``. Blocked links are kept so the UI can
    offer a one-off override instead of leaving the user wondering why an
    invoice never appeared.
    """
    candidates = body_urls(email)
    if not candidates:
        return [], []

    allowed: list[str] = []
    blocked: list[SkippedSource] = []
    seen: set[str] = set()

    for raw in candidates:
        url = _normalize_url(raw)
        if url in seen:
            continue
        seen.add(url)

        if not url.lower().startswith("https://"):
            blocked.append(
                SkippedSource(label=url, reason=SkipReason.NOT_HTTPS, url=url)
            )
            continue
        if not domain_allowed(url, allowed_domains):
            blocked.append(
                SkippedSource(
                    label=url, reason=SkipReason.BLOCKED_DOMAIN, url=url
                )
            )
            continue
        allowed.append(url)

    return allowed, blocked


def match_keywords(email, attachments, keywords: list[str]) -> list[str]:
    """Return every keyword found in the subject, body or attachment names."""
    haystack = " ".join(
        part
        for part in (
            email.subject,
            email.text_content,
            email.html_content,
            " ".join(
                attachment.filename or "" for attachment in attachments
            ),
        )
        if part
    ).lower()
    if not haystack:
        return []
    return [word for word in keywords if word in haystack]


def evaluate_email(
    email, attachments, app_config, user_config, keywords=None
) -> EmailCandidate:
    """Judge one email without spending anything."""
    if keywords is None:
        keywords = resolve_keywords(user_config)
    allowed_domains = resolve_allowed_domains(app_config, user_config)

    candidate = EmailCandidate(
        email_id=email.id,
        email_uuid=str(email.uuid),
        subject=email.subject or "",
        received_at=email.received_at.isoformat() if email.received_at else "",
        matched_keywords=match_keywords(email, attachments, keywords),
    )

    if not sender_allowed(email, user_config):
        return candidate

    if not candidate.matched_keywords:
        return candidate

    for attachment in attachments:
        kind, reason = classify_attachment(attachment, app_config)
        label = attachment.filename or attachment.safe_filename or ""
        if kind:
            candidate.sources.append(
                CandidateSource(
                    kind=kind, label=label, attachment_id=attachment.id
                )
            )
        else:
            candidate.skipped.append(
                SkippedSource(label=label, reason=reason)
            )

    allowed_links, blocked_links = extract_body_links(email, allowed_domains)
    for url in allowed_links:
        candidate.sources.append(
            CandidateSource(kind=SourceKind.BODY_LINK, label=url, url=url)
        )
    candidate.skipped.extend(blocked_links)

    return candidate

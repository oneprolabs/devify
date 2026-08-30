"""Unit tests for the zero-cost candidate filter."""

import pytest

from expense.constants import MIN_IMAGE_BYTES
from expense.services.candidate_filter import (
    SkipReason,
    SourceKind,
    classify_attachment,
    domain_allowed,
    evaluate_email,
    extract_body_links,
    match_keywords,
    resolve_keywords,
    sender_allowed,
)


pytestmark = pytest.mark.unit


class FakeAttachment:
    def __init__(
        self,
        filename="invoice.pdf",
        content_type="application/pdf",
        file_size=100_000,
        is_image=False,
        pk=1,
    ):
        self.filename = filename
        self.safe_filename = filename
        self.content_type = content_type
        self.file_size = file_size
        self.is_image = is_image
        self.id = pk


class FakeEmail:
    def __init__(
        self,
        subject="您的发票",
        text_content="",
        html_content="",
        sender="billing@example.com",
        pk=1,
    ):
        self.id = pk
        self.uuid = "00000000-0000-0000-0000-000000000001"
        self.subject = subject
        self.text_content = text_content
        self.html_content = html_content
        self.sender = sender
        self.received_at = None


class FakeAppConfig:
    max_download_bytes = 20 * 1024 * 1024
    link_domain_allowlist = ["fapiao.example.com"]


class FakeUserConfig:
    keyword_filters = []
    sender_allowlist = []
    extra_link_domains = []


class TestClassifyAttachment:
    def test_pdf_is_a_source(self):
        kind, reason = classify_attachment(FakeAttachment(), FakeAppConfig())
        assert kind == SourceKind.ATTACHMENT
        assert reason is None

    def test_pdf_recognized_by_extension_when_type_is_generic(self):
        attachment = FakeAttachment(
            content_type="application/octet-stream", filename="fapiao.PDF"
        )
        kind, _ = classify_attachment(attachment, FakeAppConfig())
        assert kind == SourceKind.ATTACHMENT

    def test_ofd_is_a_source(self):
        attachment = FakeAttachment(
            filename="invoice.ofd", content_type="application/ofd"
        )
        kind, _ = classify_attachment(attachment, FakeAppConfig())
        assert kind == SourceKind.ATTACHMENT

    def test_large_image_is_a_source(self):
        attachment = FakeAttachment(
            filename="photo.jpg", content_type="image/jpeg", is_image=True
        )
        kind, _ = classify_attachment(attachment, FakeAppConfig())
        assert kind == SourceKind.ATTACHMENT

    def test_tiny_image_is_skipped_as_a_signature(self):
        attachment = FakeAttachment(
            filename="logo.png",
            content_type="image/png",
            file_size=MIN_IMAGE_BYTES - 1,
            is_image=True,
        )
        kind, reason = classify_attachment(attachment, FakeAppConfig())
        assert kind is None
        assert reason == SkipReason.TOO_SMALL

    def test_oversized_file_is_skipped(self):
        attachment = FakeAttachment(file_size=50 * 1024 * 1024)
        kind, reason = classify_attachment(attachment, FakeAppConfig())
        assert kind is None
        assert reason == SkipReason.TOO_LARGE

    def test_eml_waits_on_the_ingestion_dependency(self):
        attachment = FakeAttachment(
            filename="forwarded.eml", content_type="message/rfc822"
        )
        kind, reason = classify_attachment(attachment, FakeAppConfig())
        assert kind is None
        assert reason == SkipReason.PENDING_DEPENDENCY

    def test_unrelated_type_is_skipped(self):
        attachment = FakeAttachment(
            filename="notes.docx",
            content_type=(
                "application/vnd.openxmlformats-officedocument"
                ".wordprocessingml.document"
            ),
        )
        kind, reason = classify_attachment(attachment, FakeAppConfig())
        assert kind is None
        assert reason == SkipReason.UNSUPPORTED_TYPE


class TestDomainAllowlist:
    def test_exact_host_matches(self):
        assert domain_allowed(
            "https://fapiao.example.com/a", ["fapiao.example.com"]
        )

    def test_subdomain_matches(self):
        assert domain_allowed(
            "https://cdn.fapiao.example.com/a", ["fapiao.example.com"]
        )

    def test_lookalike_suffix_does_not_match(self):
        # evilfapiao.example.com must not pass as fapiao.example.com.
        assert not domain_allowed(
            "https://evilfapiao.example.com/a", ["fapiao.example.com"]
        )

    def test_unrelated_host_does_not_match(self):
        assert not domain_allowed(
            "https://elsewhere.test/a", ["fapiao.example.com"]
        )


class TestExtractBodyLinks:
    def test_allowlisted_https_link_is_kept(self):
        email = FakeEmail(
            text_content="下载: https://fapiao.example.com/d/123 谢谢"
        )
        allowed, blocked = extract_body_links(email, ["fapiao.example.com"])
        assert allowed == ["https://fapiao.example.com/d/123"]
        assert blocked == []

    def test_http_link_is_blocked(self):
        email = FakeEmail(text_content="http://fapiao.example.com/d/1")
        allowed, blocked = extract_body_links(email, ["fapiao.example.com"])
        assert allowed == []
        assert blocked[0].reason == SkipReason.NOT_HTTPS

    def test_unlisted_domain_is_blocked_but_reported(self):
        email = FakeEmail(text_content="https://random.test/invoice.pdf")
        allowed, blocked = extract_body_links(email, ["fapiao.example.com"])
        assert allowed == []
        assert blocked[0].reason == SkipReason.BLOCKED_DOMAIN

    def test_trailing_punctuation_is_trimmed(self):
        email = FakeEmail(
            text_content="请见 https://fapiao.example.com/d/9。"
        )
        allowed, _ = extract_body_links(email, ["fapiao.example.com"])
        assert allowed == ["https://fapiao.example.com/d/9"]

    def test_chinese_text_right_after_the_link_is_not_swallowed(self):
        email = FakeEmail(
            text_content="见 https://fapiao.example.com/d/9，谢谢"
        )
        allowed, _ = extract_body_links(email, ["fapiao.example.com"])
        assert allowed == ["https://fapiao.example.com/d/9"]

    def test_percent_encoded_path_survives(self):
        url = "https://fapiao.example.com/%E5%8F%91%E7%A5%A8.pdf"
        email = FakeEmail(text_content=url)
        allowed, _ = extract_body_links(email, ["fapiao.example.com"])
        assert allowed == [url]

    def test_duplicate_links_collapse(self):
        url = "https://fapiao.example.com/d/1"
        email = FakeEmail(
            text_content=url, html_content=f'<a href="{url}">x</a>'
        )
        allowed, _ = extract_body_links(email, ["fapiao.example.com"])
        assert allowed == [url]


class TestKeywords:
    def test_user_keywords_replace_the_defaults(self):
        config = FakeUserConfig()
        config.keyword_filters = ["Custom"]
        assert resolve_keywords(config) == ["custom"]

    def test_defaults_apply_when_unset(self):
        assert "发票" in resolve_keywords(FakeUserConfig())

    def test_subject_match_is_found(self):
        matched = match_keywords(FakeEmail(subject="您的发票"), [], ["发票"])
        assert matched == ["发票"]

    def test_attachment_name_match_is_found(self):
        matched = match_keywords(
            FakeEmail(subject="hello"),
            [FakeAttachment(filename="invoice-2026.pdf")],
            ["invoice"],
        )
        assert matched == ["invoice"]


class TestSenderAllowlist:
    def test_empty_allowlist_accepts_everyone(self):
        assert sender_allowed(FakeEmail(), FakeUserConfig())

    def test_listed_sender_passes(self):
        config = FakeUserConfig()
        config.sender_allowlist = ["billing@example.com"]
        assert sender_allowed(FakeEmail(), config)

    def test_unlisted_sender_is_rejected(self):
        config = FakeUserConfig()
        config.sender_allowlist = ["other@example.com"]
        assert not sender_allowed(FakeEmail(), config)


class TestEvaluateEmail:
    def test_keyword_hit_with_pdf_is_a_candidate(self):
        verdict = evaluate_email(
            FakeEmail(),
            [FakeAttachment()],
            FakeAppConfig(),
            FakeUserConfig(),
        )
        assert verdict.is_candidate
        assert verdict.sources[0].kind == SourceKind.ATTACHMENT

    def test_no_keyword_means_no_candidate_even_with_a_pdf(self):
        verdict = evaluate_email(
            FakeEmail(subject="周报"),
            [FakeAttachment(filename="report.pdf")],
            FakeAppConfig(),
            FakeUserConfig(),
        )
        assert not verdict.is_candidate

    def test_keyword_without_any_usable_source_is_not_a_candidate(self):
        verdict = evaluate_email(
            FakeEmail(subject="发票已寄出"),
            [],
            FakeAppConfig(),
            FakeUserConfig(),
        )
        assert not verdict.is_candidate

    def test_body_link_alone_can_make_a_candidate(self):
        verdict = evaluate_email(
            FakeEmail(
                subject="您的发票",
                text_content="https://fapiao.example.com/d/1",
            ),
            [],
            FakeAppConfig(),
            FakeUserConfig(),
        )
        assert verdict.is_candidate
        assert verdict.sources[0].kind == SourceKind.BODY_LINK

    def test_blocked_link_is_reported_but_does_not_qualify(self):
        verdict = evaluate_email(
            FakeEmail(
                subject="您的发票",
                text_content="https://random.test/i.pdf",
            ),
            [],
            FakeAppConfig(),
            FakeUserConfig(),
        )
        assert not verdict.is_candidate
        assert verdict.skipped[0].reason == SkipReason.BLOCKED_DOMAIN

    def test_sender_allowlist_excludes_the_email_entirely(self):
        config = FakeUserConfig()
        config.sender_allowlist = ["nobody@example.com"]
        verdict = evaluate_email(
            FakeEmail(), [FakeAttachment()], FakeAppConfig(), config
        )
        assert not verdict.is_candidate

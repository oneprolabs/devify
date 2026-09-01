"""
Choosing which links in an email actually fetch an invoice.

Structure removes what the mail client renders, but 「下载发票」 and an
advertisement are both anchors a person could click, and only the words
tell them apart. Every wrong guess costs a request, a stored failure and a
line in the user's pending list.
"""

from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.utils import timezone

from expense.models import Invoice, InvoiceSourceFile
from expense.services.config_service import get_app_config
from expense.services.link_picker import pick_invoice_links, render_links
from expense.services.recognition import recognize_email
from threadline.models import EmailMessage


pytestmark = [pytest.mark.integration, pytest.mark.django_db]

PICK_PATH = "expense.services.link_picker.LLMTracker.call_messages_and_track"
FETCH_PATH = "expense.services.recognition.fetch_link"

ANCHORS = [
    {"url": "https://ads.example.com/h5", "text": "立即领取优惠券"},
    {"url": "https://fapiao.example.com/d/9f2c", "text": "下载发票"},
    {"url": "https://help.example.com/faq", "text": "查看帮助"},
]


def make_email(user, html="", counter=[0]):
    counter[0] += 1
    return EmailMessage.objects.create(
        user=user,
        message_id=f"email_pick_{counter[0]:04d}",
        subject="您的电子发票已开具",
        sender="billing@example.com",
        recipients="user@example.com",
        html_content=html,
        received_at=timezone.now() - timedelta(hours=1),
    )


def html_with(anchors):
    return "".join(
        f'<a href="{a["url"]}">{a["text"]}</a>' for a in anchors
    ) + '<img src="https://cdn.example.com/images/mail/mail_line.jpg">'


def _refused_fetch():
    """A fetch that failed cleanly, so the run ends without a download."""
    return SimpleNamespace(
        status="requires_auth",
        error="login required",
        final_url="",
        content_type="text/html",
        file_size=0,
        file_path="",
        content_md5="",
        ok=False,
    )


class TestPicker:
    def test_only_the_named_link_is_kept(self):
        with patch(PICK_PATH) as call:
            call.return_value = ({"invoice_links": [1]}, None)
            picked = pick_invoice_links("您的电子发票", ANCHORS, "m-1")

        assert [a["url"] for a in picked] == [
            "https://fapiao.example.com/d/9f2c"
        ]

    def test_it_can_keep_nothing(self):
        # An email whose invoice is attached has no link worth following.
        with patch(PICK_PATH) as call:
            call.return_value = ({"invoice_links": []}, None)

            assert pick_invoice_links("您的电子发票", ANCHORS, "m-1") == []

    def test_the_link_text_reaches_the_model(self):
        rendered = render_links(ANCHORS)

        assert "下载发票" in rendered
        assert "https://fapiao.example.com/d/9f2c" in rendered

    def test_a_failure_follows_everything(self):
        # Missing a real invoice is worse than fetching an advert, so the
        # model going wrong must not silently drop links.
        with patch(PICK_PATH, side_effect=RuntimeError("model down")):
            picked = pick_invoice_links("您的电子发票", ANCHORS, "m-1")

        assert picked == ANCHORS

    def test_nonsense_indexes_are_ignored(self):
        with patch(PICK_PATH) as call:
            call.return_value = ({"invoice_links": [1, 99, "x"]}, None)
            picked = pick_invoice_links("您的电子发票", ANCHORS, "m-1")

        assert len(picked) == 1

    def test_no_model_configured_follows_everything(self):
        assert pick_invoice_links("您的电子发票", ANCHORS, "") == ANCHORS

    def test_no_links_asks_nothing(self):
        with patch(PICK_PATH) as call:
            assert pick_invoice_links("您的电子发票", [], "m-1") == []

        call.assert_not_called()


class TestPickingDuringRecognition:
    @pytest.fixture(autouse=True)
    def _model(self, db):
        config = get_app_config()
        config.text_llm_config_uuid = "22222222-2222-2222-2222-222222222222"
        config.llm_config_uuid = "11111111-1111-1111-1111-111111111111"
        config.save()
        return config

    def test_the_advert_is_never_fetched(self, user):
        email = make_email(user, html=html_with(ANCHORS))

        with patch(PICK_PATH) as pick, patch(FETCH_PATH) as fetch:
            pick.return_value = ({"invoice_links": [1]}, None)
            fetch.return_value = _refused_fetch()
            recognize_email(email)

        fetched = [call.args[0] for call in fetch.call_args_list]
        assert fetched == ["https://fapiao.example.com/d/9f2c"]

    def test_nothing_is_fetched_when_nothing_was_chosen(self, user):
        email = make_email(user, html=html_with(ANCHORS))

        with patch(PICK_PATH) as pick, patch(FETCH_PATH) as fetch:
            pick.return_value = ({"invoice_links": []}, None)
            recognize_email(email)

        fetch.assert_not_called()

    def test_a_rejected_link_leaves_no_pending_row(self, user):
        # The user's list should not fill up with adverts to allow.
        email = make_email(user, html=html_with(ANCHORS))

        with patch(PICK_PATH) as pick, patch(FETCH_PATH):
            pick.return_value = ({"invoice_links": []}, None)
            recognize_email(email)

        assert InvoiceSourceFile.objects.filter(
            email_message=email
        ).count() == 0

    def test_no_invoice_is_created_by_the_choice_alone(self, user):
        email = make_email(user, html=html_with(ANCHORS))

        with patch(PICK_PATH) as pick, patch(FETCH_PATH) as fetch:
            pick.return_value = ({"invoice_links": []}, None)
            recognize_email(email)

        assert Invoice.objects.filter(email_message=email).count() == 0


class TestPreviewStaysFree:
    def test_estimating_a_scan_calls_no_model(self, user):
        # The preview exists to state a price before anything is spent, so
        # it must not spend anything itself.
        from expense.services.config_service import set_user_enabled
        from expense.services.config_service import get_user_config
        from expense.services.scanner import preview_scan

        set_user_enabled(get_user_config(user), True)
        make_email(user, html=html_with(ANCHORS))

        with patch(PICK_PATH) as pick:
            preview_scan(user, lookback_days=30)

        pick.assert_not_called()

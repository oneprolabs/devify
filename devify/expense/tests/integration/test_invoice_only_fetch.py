"""
Fetching only the invoices from a mailbox.

An email that is never fetched is never processed and never charged, so
this filter is the cheapest one there is. It also has to be the safest:
the server decides what to send, but the decision that matters is made
again here, because a real IMAP server answered OK to a body search and
returned the whole mailbox.
"""

import pytest

from expense.services.routing import says_invoice, subject_terms
from threadline.models import EmailMailbox
from threadline.utils.email.clients.imap import IMAPClient
from threadline.utils.email.processor import EmailProcessor


pytestmark = [pytest.mark.integration, pytest.mark.django_db]


def make_mailbox(user, invoice_only=False, counter=[0]):
    counter[0] += 1
    return EmailMailbox.objects.create(
        user=user,
        name=f"box-{counter[0]}",
        imap_host=f"imap{counter[0]}.example.com",
        imap_port=993,
        username=f"user{counter[0]}@example.com",
        password="secret",
        invoice_only=invoice_only,
    )


class TestSearchCriteria:
    def _client(self, filter_config):
        return IMAPClient(
            imap_config={"imap_host": "imap.example.com"},
            filter_config=filter_config,
        )

    def test_several_words_become_a_nested_or(self):
        # Listed plainly they would be ANDed, demanding a subject that
        # contains all of them, which matches nothing.
        client = self._client({"subject_any": ["发票", "行程单", "车票"]})

        assert client.search_criteria == (
            'OR SUBJECT "发票" OR SUBJECT "行程单" SUBJECT "车票"'
        )

    def test_one_word_needs_no_or(self):
        client = self._client({"subject_any": ["发票"]})

        assert client.search_criteria == 'SUBJECT "发票"'

    def test_it_combines_with_the_other_conditions(self):
        client = self._client(
            {"subject_any": ["发票"], "filters": ["unread:"]}
        )

        assert client.search_criteria == 'UNSEEN SUBJECT "发票"'

    def test_no_words_leaves_the_search_alone(self):
        client = self._client({})

        assert client.search_criteria == "ALL"


class TestMailboxConfig:
    def test_the_toggle_reaches_the_fetch_config(self, user):
        mailbox = make_mailbox(user, invoice_only=True)

        config = mailbox.to_email_config()

        assert config["filter_config"]["subject_any"]

    def test_it_is_off_by_default(self, user):
        mailbox = make_mailbox(user)

        config = mailbox.to_email_config()

        assert "subject_any" not in config["filter_config"]

    def test_the_mailbox_filters_apply_alongside_the_subject_search(
        self, user
    ):
        # Narrowing to invoices does not replace the mailbox's own rules;
        # both reach the IMAP search together.
        mailbox = make_mailbox(user, invoice_only=True)
        mailbox.max_age_days = 7
        mailbox.save(update_fields=["max_age_days"])

        config = mailbox.to_email_config()

        assert config["filter_config"]["max_age_days"] == 7
        assert config["filter_config"]["subject_any"]

    def test_redundant_keywords_are_dropped(self, user):
        # IMAP matches substrings, so 电子发票 can never add a result that
        # 发票 did not already return, and every extra term deepens the
        # nested OR the server has to parse.
        terms = subject_terms(user)

        assert "发票" in terms
        assert "电子发票" not in terms


class TestLocalDecision:
    def _processor(self, terms):
        processor = EmailProcessor.__new__(EmailProcessor)
        processor.filter_config = {"subject_any": terms}
        return processor

    def test_a_subject_that_names_an_invoice_is_kept(self):
        processor = self._processor(["发票"])

        assert processor._wanted({"subject": "【电子发票】北京麻六记"}) is True

    def test_an_attachment_name_is_enough(self):
        processor = self._processor(["发票"])

        kept = processor._wanted(
            {
                "subject": "转发：上月费用",
                "attachments": [{"filename": "电子发票_209.20元.pdf"}],
            }
        )

        assert kept is True

    def test_ordinary_mail_is_dropped(self):
        processor = self._processor(["发票"])

        assert processor._wanted({"subject": "【北京移动】话费账单"}) is False

    def test_the_body_does_not_count(self):
        # The body is what made the scan filter match every phone bill
        # that mentioned 发票 in a footer.
        processor = self._processor(["发票"])

        kept = processor._wanted(
            {"subject": "周会纪要", "text_content": "发票的事下周说"}
        )

        assert kept is False

    def test_a_server_that_ignored_the_criteria_is_corrected_here(self):
        # 139.com answers OK to a body search and returns everything.
        # Deciding again locally means that costs traffic, not accuracy.
        processor = self._processor(["发票"])
        everything = [
            {"subject": "【电子发票】北京麻六记"},
            {"subject": "【北京移动】话费账单"},
            {"subject": "139邮箱使用报告"},
        ]

        kept = [row for row in everything if processor._wanted(row)]

        assert len(kept) == 1

    def test_without_the_toggle_everything_passes(self):
        processor = EmailProcessor.__new__(EmailProcessor)
        processor.filter_config = {}

        assert processor._wanted({"subject": "周会纪要"}) is True


class TestSharedRule:
    def test_the_fetch_and_the_routing_rule_agree(self, user):
        # Both sides answer "does this email say invoice", and they must
        # answer it the same way or mail is fetched then ignored.
        terms = subject_terms(user)

        assert says_invoice("【电子发票】北京麻六记", [], terms) is True
        assert says_invoice("【北京移动】话费账单", [], terms) is False
        assert says_invoice(
            "转发：上月费用", ["电子发票_209.20元.pdf"], terms
        ) is True

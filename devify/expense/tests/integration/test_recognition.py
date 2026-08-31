"""
Integration tests for recognition and what it charges.

The model is mocked throughout: these assert the billing rule and the
deduplication behaviour, not the quality of the model's reading.
"""

from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.utils import timezone

from billing.models import EmailCreditsTransaction, UserCredits
from billing.services.credits_service import CreditsService
from expense.models import Invoice
from expense.services.config_service import get_app_config
from expense.services.decoder import DecodedSource, DecodeMode
from expense.services.recognition import Outcome, recognize_email
from threadline.models import EmailAttachment, EmailMessage


pytestmark = [pytest.mark.integration, pytest.mark.django_db]

EXTRACT_PATH = "expense.services.recognition.extract"
DECODE_PATH = "expense.services.recognition.decode_source"


def invoice_fields(**overrides):
    fields = {
        "is_invoice": True,
        "invoice_type": "vat_electronic",
        "invoice_no": "25117000000012345678",
        "invoice_code": "",
        "issue_date": timezone.now().date(),
        "expense_date": timezone.now().date(),
        "seller_name": "滴滴出行",
        "seller_tax_id": "",
        "buyer_name": "",
        "buyer_tax_id": "",
        "total_amount": Decimal("128.50"),
        "tax_amount": Decimal("7.55"),
        "amount_excl_tax": Decimal("120.95"),
        "currency": "CNY",
        "city": "上海",
        "category": "transport_local",
        "category_source": "model",
        "items": [],
        "ticket_details": {},
        "confidence": 0.95,
        "needs_review": False,
        "amounts_consistent": True,
        "raw_extraction": {"is_invoice": True},
    }
    fields.update(overrides)
    return fields


def make_email(user, counter=[0]):
    counter[0] += 1
    return EmailMessage.objects.create(
        user=user,
        message_id=f"email_reco_{counter[0]:04d}",
        subject="您的电子发票",
        sender="billing@example.com",
        recipients="user@example.com",
        received_at=timezone.now() - timedelta(hours=1),
    )


def attach(user, email, filename="invoice.pdf", md5=None, counter=[0]):
    counter[0] += 1
    return EmailAttachment.objects.create(
        user=user,
        email_message=email,
        filename=filename,
        safe_filename=filename,
        content_type="application/pdf",
        file_size=120_000,
        file_path=f"/tmp/{filename}",
        content_md5=md5 or f"{counter[0]:032d}",
    )


def give_credits(user, amount):
    # The credits row is created lazily on first access, so make sure it
    # exists before topping it up.
    CreditsService.get_user_credits(user.id)
    credits = UserCredits.objects.get(user_id=user.id, is_active=True)
    credits.base_credits = amount
    credits.consumed_credits = 0
    credits.save(update_fields=["base_credits", "consumed_credits"])
    return credits


def stub_decode():
    return patch(
        DECODE_PATH,
        return_value=DecodedSource(
            mode=DecodeMode.TEXT, text="发票 " * 40, decoder="pdf_text_layer"
        ),
    )


@pytest.fixture(autouse=True)
def _configured_model(db):
    config = get_app_config()
    config.llm_config_uuid = "11111111-1111-1111-1111-111111111111"
    config.text_llm_config_uuid = "22222222-2222-2222-2222-222222222222"
    config.save()
    return config


class TestBillingRule:
    def test_one_invoice_costs_one_credit(self, user):
        give_credits(user, 10)
        email = make_email(user)
        attach(user, email)

        with stub_decode(), patch(EXTRACT_PATH, return_value=invoice_fields()):
            stats = recognize_email(email)

        assert stats["extracted"] == 1
        assert stats["credits_consumed"] == 1

    def test_many_invoices_in_one_email_still_cost_one_credit(self, user):
        give_credits(user, 10)
        email = make_email(user)
        for index in range(5):
            attach(user, email, filename=f"invoice-{index}.pdf")

        side_effect = [
            invoice_fields(invoice_no=f"INV-{index}") for index in range(5)
        ]
        with stub_decode(), patch(EXTRACT_PATH, side_effect=side_effect):
            stats = recognize_email(email)

        assert stats["extracted"] == 5
        assert stats["credits_consumed"] == 1
        assert EmailCreditsTransaction.objects.count() == 1

    def test_email_without_an_invoice_is_free(self, user):
        give_credits(user, 10)
        email = make_email(user)
        attach(user, email)

        with stub_decode(), patch(
            EXTRACT_PATH, return_value={"is_invoice": False}
        ):
            stats = recognize_email(email)

        assert stats["not_invoice"] == 1
        assert stats["credits_consumed"] == 0
        assert EmailCreditsTransaction.objects.count() == 0

    def test_failed_extraction_is_free(self, user):
        give_credits(user, 10)
        email = make_email(user)
        attach(user, email)

        with stub_decode(), patch(
            EXTRACT_PATH, side_effect=RuntimeError("model exploded")
        ):
            stats = recognize_email(email)

        assert stats["failed"] == 1
        assert stats["credits_consumed"] == 0
        assert EmailCreditsTransaction.objects.count() == 0
        assert (
            Invoice.objects.get(email_message=email).status
            == Invoice.Status.FAILED
        )

    def test_rerunning_the_same_email_does_not_charge_twice(self, user):
        give_credits(user, 10)
        email = make_email(user)
        attach(user, email)

        with stub_decode(), patch(EXTRACT_PATH, return_value=invoice_fields()):
            recognize_email(email)
            second = recognize_email(email)

        assert second["credits_consumed"] == 0
        assert EmailCreditsTransaction.objects.count() == 1

    def test_forced_rerun_charges_again(self, user):
        give_credits(user, 10)
        email = make_email(user)
        attach(user, email)

        with stub_decode(), patch(EXTRACT_PATH, return_value=invoice_fields()):
            recognize_email(email)
            forced = recognize_email(email, force=True)

        assert forced["credits_consumed"] == 1
        assert EmailCreditsTransaction.objects.count() == 2

    def test_empty_balance_skips_before_calling_the_model(self, user):
        give_credits(user, 0)
        email = make_email(user)
        attach(user, email)

        with stub_decode(), patch(EXTRACT_PATH) as extract_mock:
            stats = recognize_email(email)

        assert stats["outcome"] == Outcome.INSUFFICIENT_CREDITS
        extract_mock.assert_not_called()
        assert (
            Invoice.objects.get(email_message=email).status
            == Invoice.Status.INSUFFICIENT_CREDITS
        )

    def test_charge_is_linked_to_the_invoices(self, user):
        give_credits(user, 10)
        email = make_email(user)
        attach(user, email)

        with stub_decode(), patch(EXTRACT_PATH, return_value=invoice_fields()):
            recognize_email(email)

        invoice = Invoice.objects.get(email_message=email)
        assert invoice.credits_transaction is not None
        assert invoice.credits_transaction.reason == "invoice_extraction"

    def test_balance_drops_by_exactly_one(self, user):
        credits = give_credits(user, 10)
        before = credits.available_credits
        email = make_email(user)
        attach(user, email, filename="a.pdf")
        attach(user, email, filename="b.pdf")

        with stub_decode(), patch(
            EXTRACT_PATH,
            side_effect=[
                invoice_fields(invoice_no="A"),
                invoice_fields(invoice_no="B"),
            ],
        ):
            recognize_email(email)

        credits.refresh_from_db()
        assert before - credits.available_credits == 1


class TestDeduplication:
    def test_same_invoice_number_in_a_later_email_is_a_duplicate(self, user):
        give_credits(user, 10)
        first = make_email(user)
        attach(user, first, filename="first.pdf")
        second = make_email(user)
        attach(user, second, filename="second.pdf")

        with stub_decode(), patch(EXTRACT_PATH, return_value=invoice_fields()):
            recognize_email(first)
            stats = recognize_email(second)

        assert stats["duplicates"] == 1
        assert stats["extracted"] == 0

    def test_a_duplicate_only_email_is_free(self, user):
        give_credits(user, 10)
        first = make_email(user)
        attach(user, first, filename="first.pdf")
        second = make_email(user)
        attach(user, second, filename="second.pdf")

        with stub_decode(), patch(EXTRACT_PATH, return_value=invoice_fields()):
            recognize_email(first)
            recognize_email(second)

        assert EmailCreditsTransaction.objects.count() == 1

    def test_duplicate_points_back_at_the_original(self, user):
        give_credits(user, 10)
        first = make_email(user)
        attach(user, first, filename="first.pdf")
        second = make_email(user)
        attach(user, second, filename="second.pdf")

        with stub_decode(), patch(EXTRACT_PATH, return_value=invoice_fields()):
            recognize_email(first)
            recognize_email(second)

        copy = Invoice.objects.get(
            email_message=second, status=Invoice.Status.DUPLICATE
        )
        assert copy.duplicate_of.email_message_id == first.id

    def test_a_ticket_without_a_number_dedups_on_the_file(self, user):
        give_credits(user, 10)
        shared_md5 = "f" * 32
        first = make_email(user)
        attach(user, first, filename="ticket-1.pdf", md5=shared_md5)
        second = make_email(user)
        attach(user, second, filename="ticket-2.pdf", md5=shared_md5)

        fields = invoice_fields(invoice_no="", invoice_type="train")
        with stub_decode(), patch(EXTRACT_PATH, return_value=fields):
            recognize_email(first)
            stats = recognize_email(second)

        assert stats["duplicates"] == 1

    def test_different_invoices_both_land(self, user):
        give_credits(user, 10)
        email = make_email(user)
        attach(user, email, filename="a.pdf")
        attach(user, email, filename="b.pdf")

        with stub_decode(), patch(
            EXTRACT_PATH,
            side_effect=[
                invoice_fields(invoice_no="AAA"),
                invoice_fields(invoice_no="BBB"),
            ],
        ):
            stats = recognize_email(email)

        assert stats["extracted"] == 2
        assert Invoice.objects.filter(
            status=Invoice.Status.EXTRACTED
        ).count() == 2

    def test_the_same_number_for_a_different_user_is_not_a_duplicate(
        self, user, other_user
    ):
        give_credits(user, 10)
        give_credits(other_user, 10)
        mine = make_email(user)
        attach(user, mine, filename="mine.pdf")
        theirs = make_email(other_user)
        attach(other_user, theirs, filename="theirs.pdf")

        with stub_decode(), patch(EXTRACT_PATH, return_value=invoice_fields()):
            recognize_email(mine)
            stats = recognize_email(theirs)

        assert stats["extracted"] == 1


class TestModelRouting:
    def test_text_decodes_use_the_cheap_model(self, user):
        give_credits(user, 10)
        email = make_email(user)
        attach(user, email)

        with stub_decode(), patch(
            EXTRACT_PATH, return_value=invoice_fields()
        ) as extract_mock:
            recognize_email(email)

        model_uuid = extract_mock.call_args.args[3]
        assert model_uuid == "22222222-2222-2222-2222-222222222222"

    def test_rendered_pages_use_the_vision_model(self, user):
        give_credits(user, 10)
        email = make_email(user)
        attach(user, email)

        decoded = DecodedSource(
            mode=DecodeMode.IMAGE,
            images=[("image/png", b"x")],
            decoder="pdf_render",
        )
        with patch(DECODE_PATH, return_value=decoded), patch(
            EXTRACT_PATH, return_value=invoice_fields()
        ) as extract_mock:
            recognize_email(email)

        model_uuid = extract_mock.call_args.args[3]
        assert model_uuid == "11111111-1111-1111-1111-111111111111"


class TestExpenseDate:
    def test_the_travel_date_is_stored_not_just_the_issue_date(self, user):
        # A July journey invoiced in August has to keep both dates, or
        # grouping files the trip a month out.
        give_credits(user, 10)
        email = make_email(user)
        attach(user, email)
        fields = invoice_fields(
            invoice_type="train",
            issue_date=date(2026, 8, 6),
            expense_date=date(2026, 7, 20),
            ticket_details={"depart_at": "2026-07-20 06:52"},
        )

        with stub_decode(), patch(EXTRACT_PATH, return_value=fields):
            recognize_email(email)

        invoice = Invoice.objects.get(email_message=email)
        assert invoice.issue_date == date(2026, 8, 6)
        assert invoice.expense_date == date(2026, 7, 20)


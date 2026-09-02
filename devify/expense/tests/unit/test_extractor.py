"""Unit tests for extraction normalization and validation."""

from datetime import date
from decimal import Decimal

import pytest

from expense.constants import ExpenseCategory
from expense.models import Invoice
from expense.services.extractor import (
    check_amounts,
    normalize,
    resolve_category,
    resolve_expense_date,
)


pytestmark = pytest.mark.unit


def raw_invoice(**overrides):
    payload = {
        "is_invoice": True,
        "invoice_type": "vat_electronic",
        "invoice_no": "25117000000012345678",
        "issue_date": "2026-08-12",
        "seller_name": "滴滴出行科技有限公司",
        "total_amount": 128.50,
        "tax_amount": 7.55,
        "amount_excl_tax": 120.95,
        "category": "transport_local",
        "confidence": 0.95,
    }
    payload.update(overrides)
    return payload


class TestCheckAmounts:
    def test_consistent_amounts_pass(self):
        assert check_amounts(
            Decimal("128.50"), Decimal("7.55"), Decimal("120.95")
        )

    def test_one_cent_rounding_is_tolerated(self):
        assert check_amounts(
            Decimal("128.50"), Decimal("7.55"), Decimal("120.96")
        )

    def test_real_mismatch_fails(self):
        assert not check_amounts(
            Decimal("128.50"), Decimal("7.55"), Decimal("100.00")
        )

    def test_missing_pieces_cannot_contradict(self):
        # A taxi receipt has no tax breakdown; that is not a red flag.
        assert check_amounts(Decimal("128.50"), None, None)


class TestResolveCategory:
    def test_train_ticket_is_classified_without_the_model(self):
        category, source = resolve_category("train", "meals")
        assert category == ExpenseCategory.TRANSPORT_LONG
        assert source == Invoice.CategorySource.RULE

    def test_hotel_invoice_maps_to_accommodation(self):
        category, source = resolve_category("hotel", "")
        assert category == ExpenseCategory.ACCOMMODATION
        assert source == Invoice.CategorySource.RULE

    def test_generic_invoice_uses_the_model_answer(self):
        category, source = resolve_category("vat_electronic", "meals")
        assert category == ExpenseCategory.MEALS
        assert source == Invoice.CategorySource.MODEL

    def test_unknown_category_falls_back_to_other(self):
        category, _ = resolve_category("vat_electronic", "spaceflight")
        assert category == ExpenseCategory.OTHER


class TestNormalize:
    def test_negative_verdict_short_circuits(self):
        result = normalize({"is_invoice": False, "total_amount": 999})
        assert result == {"is_invoice": False}

    def test_amounts_become_decimals(self):
        result = normalize(raw_invoice())
        assert result["total_amount"] == Decimal("128.50")
        assert result["tax_amount"] == Decimal("7.55")

    def test_currency_symbols_and_separators_are_stripped(self):
        result = normalize(raw_invoice(total_amount="¥1,286.50"))
        assert result["total_amount"] == Decimal("1286.50")

    def test_chinese_date_format_is_parsed(self):
        result = normalize(raw_invoice(issue_date="2026年08月12日"))
        assert result["issue_date"].isoformat() == "2026-08-12"

    def test_unparseable_date_becomes_none(self):
        assert normalize(raw_invoice(issue_date="不详"))["issue_date"] is None

    def test_unknown_invoice_type_falls_back_to_other(self):
        result = normalize(raw_invoice(invoice_type="magic_ticket"))
        assert result["invoice_type"] == Invoice.InvoiceType.OTHER

    def test_inconsistent_amounts_flag_review(self):
        result = normalize(raw_invoice(amount_excl_tax=1.0))
        assert result["needs_review"] is True
        assert result["amounts_consistent"] is False

    def test_low_confidence_flags_review(self):
        assert normalize(raw_invoice(confidence=0.2))["needs_review"] is True

    def test_clean_invoice_is_not_flagged(self):
        assert normalize(raw_invoice())["needs_review"] is False

    def test_ticket_details_survive_for_non_standard_tickets(self):
        result = normalize(
            raw_invoice(
                invoice_type="train",
                invoice_no="",
                tax_amount=0,
                amount_excl_tax=128.50,
                ticket_details={"train_no": "G1234", "to_station": "上海虹桥"},
            )
        )
        assert result["ticket_details"]["train_no"] == "G1234"
        assert result["category"] == ExpenseCategory.TRANSPORT_LONG

    def test_malformed_items_do_not_break_normalization(self):
        assert normalize(raw_invoice(items="not-a-list"))["items"] == []

    def test_missing_currency_defaults_to_cny(self):
        assert normalize(raw_invoice(currency=""))["currency"] == "CNY"


class TestResolveExpenseDate:
    def test_a_travel_date_wins_over_the_issue_date(self):
        # A July journey invoiced in August belongs to July.
        issued = date(2026, 8, 6)

        resolved = resolve_expense_date({"depart_at": "2026-07-20"}, issued)

        assert resolved == date(2026, 7, 20)

    def test_a_departure_time_is_tolerated(self):
        resolved = resolve_expense_date(
            {"depart_at": "2026-07-20 06:52"}, date(2026, 8, 6)
        )

        assert resolved == date(2026, 7, 20)

    def test_a_hotel_uses_its_check_in(self):
        resolved = resolve_expense_date(
            {"check_in": "2026-07-21"}, date(2026, 8, 6)
        )

        assert resolved == date(2026, 7, 21)

    def test_it_falls_back_to_the_issue_date(self):
        assert resolve_expense_date({}, date(2026, 8, 6)) == date(2026, 8, 6)

    def test_an_unreadable_travel_date_falls_back(self):
        resolved = resolve_expense_date(
            {"depart_at": "不详"}, date(2026, 8, 6)
        )

        assert resolved == date(2026, 8, 6)


class TestNormalizeExpenseDate:
    def test_a_train_ticket_carries_its_travel_date(self):
        result = normalize(
            raw_invoice(
                invoice_type="train",
                issue_date="2026-08-06",
                ticket_details={"depart_at": "2026-07-20 06:52"},
            )
        )

        assert result["issue_date"] == date(2026, 8, 6)
        assert result["expense_date"] == date(2026, 7, 20)

    def test_an_ordinary_invoice_uses_its_issue_date(self):
        result = normalize(raw_invoice(issue_date="2026-08-12"))

        assert result["expense_date"] == date(2026, 8, 12)



class TestModelFallback:
    """
    Both model slots are optional.

    They let an operator send text to a cheap model and rendered pages to a
    multimodal one. Leaving them empty must fall back to the deployment
    default rather than refusing work the default model can do.
    """

    def test_an_empty_slot_falls_back_to_the_default(self, monkeypatch):
        from types import SimpleNamespace

        from expense.services import recognition
        from expense.services.decoder import DecodedSource, DecodeMode

        monkeypatch.setattr(
            "agentcore_metering.adapters.django.services.config_source"
            ".get_default_llm_config_uuid",
            lambda: "default-uuid",
        )
        config = SimpleNamespace(
            llm_config_uuid=None, text_llm_config_uuid=None
        )
        decoded = DecodedSource(
            mode=DecodeMode.IMAGE, images=[("image/png", b"x")]
        )

        assert recognition._model_for(decoded, config) == "default-uuid"

    def test_a_configured_slot_wins_over_the_default(self):
        from types import SimpleNamespace

        from expense.services import recognition
        from expense.services.decoder import DecodedSource, DecodeMode

        config = SimpleNamespace(
            llm_config_uuid="vision-uuid", text_llm_config_uuid="text-uuid"
        )

        text = DecodedSource(mode=DecodeMode.TEXT, text="x" * 60)
        image = DecodedSource(
            mode=DecodeMode.IMAGE, images=[("image/png", b"x")]
        )

        assert recognition._model_for(text, config) == "text-uuid"
        assert recognition._model_for(image, config) == "vision-uuid"

    def test_one_slot_covers_both_paths(self):
        from types import SimpleNamespace

        from expense.services import recognition
        from expense.services.decoder import DecodedSource, DecodeMode

        config = SimpleNamespace(
            llm_config_uuid="only-uuid", text_llm_config_uuid=None
        )
        text = DecodedSource(mode=DecodeMode.TEXT, text="x" * 60)

        assert recognition._model_for(text, config) == "only-uuid"

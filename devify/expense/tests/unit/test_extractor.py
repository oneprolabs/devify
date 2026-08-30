"""Unit tests for extraction normalization and validation."""

from decimal import Decimal

import pytest

from expense.constants import ExpenseCategory
from expense.models import Invoice
from expense.services.extractor import (
    check_amounts,
    normalize,
    resolve_category,
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

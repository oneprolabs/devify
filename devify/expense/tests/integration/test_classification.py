"""Integration tests for category resolution and the memory behind it."""

import pytest

from expense.constants import ExpenseCategory
from expense.models import CategoryRule, Invoice
from expense.services.classification import (
    classify,
    find_user_rule,
    remember_correction,
)


pytestmark = [pytest.mark.integration, pytest.mark.django_db]


def fields(**overrides):
    payload = {
        "invoice_type": "vat_electronic",
        "seller_name": "某某科技有限公司",
        "seller_tax_id": "91310000MA1FL1AB2C",
        "category": "office",
    }
    payload.update(overrides)
    return payload


def make_invoice(user, **overrides):
    from django.utils import timezone

    from threadline.models import EmailMessage

    email = EmailMessage.objects.create(
        user=user,
        message_id=f"email_cls_{Invoice.objects.count():04d}",
        subject="发票",
        sender="billing@example.com",
        recipients="user@example.com",
        received_at=timezone.now(),
    )
    payload = {
        "user": user,
        "email_message": email,
        "status": Invoice.Status.EXTRACTED,
        "invoice_type": "vat_electronic",
        "seller_name": "某某科技有限公司",
        "seller_tax_id": "91310000MA1FL1AB2C",
        "category": ExpenseCategory.OFFICE,
    }
    payload.update(overrides)
    return Invoice.objects.create(**payload)


class TestClassify:
    def test_ticket_type_decides_without_the_model(self, user):
        result = classify(user, fields(invoice_type="train", category="meals"))

        assert result["category"] == ExpenseCategory.TRANSPORT_LONG
        assert result["category_source"] == Invoice.CategorySource.RULE

    def test_model_answer_is_used_when_nothing_else_applies(self, user):
        result = classify(user, fields(category="meals"))

        assert result["category"] == ExpenseCategory.MEALS
        assert result["category_source"] == Invoice.CategorySource.MODEL

    def test_an_unknown_model_answer_falls_back_to_other(self, user):
        result = classify(user, fields(category="teleportation"))

        assert result["category"] == ExpenseCategory.OTHER

    def test_a_remembered_correction_wins_over_the_model(self, user):
        CategoryRule.objects.create(
            user=user,
            match_type=CategoryRule.MatchType.SELLER_TAX_ID,
            match_value="91310000MA1FL1AB2C",
            category=ExpenseCategory.ENTERTAINMENT,
        )

        result = classify(user, fields(category="office"))

        assert result["category"] == ExpenseCategory.ENTERTAINMENT
        assert result["category_source"] == Invoice.CategorySource.USER_RULE

    def test_a_correction_also_wins_over_the_ticket_mapping(self, user):
        # The mapping is a default; the user disagreeing with it is not
        # something a default should quietly overwrite every time.
        CategoryRule.objects.create(
            user=user,
            match_type=CategoryRule.MatchType.SELLER_NAME,
            match_value="铁路客运",
            category=ExpenseCategory.OTHER,
        )

        result = classify(
            user,
            fields(
                invoice_type="train",
                seller_name="铁路客运",
                seller_tax_id="",
            ),
        )

        assert result["category"] == ExpenseCategory.OTHER
        assert result["category_source"] == Invoice.CategorySource.USER_RULE

    def test_a_matched_rule_records_the_hit(self, user):
        rule = CategoryRule.objects.create(
            user=user,
            match_type=CategoryRule.MatchType.SELLER_TAX_ID,
            match_value="91310000MA1FL1AB2C",
            category=ExpenseCategory.MEALS,
        )

        classify(user, fields())
        rule.refresh_from_db()

        assert rule.hit_count == 1

    def test_another_users_rule_does_not_apply(self, user, other_user):
        CategoryRule.objects.create(
            user=other_user,
            match_type=CategoryRule.MatchType.SELLER_TAX_ID,
            match_value="91310000MA1FL1AB2C",
            category=ExpenseCategory.ENTERTAINMENT,
        )

        result = classify(user, fields(category="office"))

        assert result["category"] == ExpenseCategory.OFFICE
        assert result["category_source"] == Invoice.CategorySource.MODEL


class TestFindUserRule:
    def test_tax_id_is_preferred_over_the_name(self, user):
        CategoryRule.objects.create(
            user=user,
            match_type=CategoryRule.MatchType.SELLER_NAME,
            match_value="某某科技有限公司",
            category=ExpenseCategory.OFFICE,
        )
        CategoryRule.objects.create(
            user=user,
            match_type=CategoryRule.MatchType.SELLER_TAX_ID,
            match_value="91310000MA1FL1AB2C",
            category=ExpenseCategory.MEALS,
        )

        rule = find_user_rule(
            user,
            seller_name="某某科技有限公司",
            seller_tax_id="91310000MA1FL1AB2C",
        )

        assert rule.category == ExpenseCategory.MEALS

    def test_no_rule_returns_none(self, user):
        assert find_user_rule(user, seller_name="未知") is None


class TestRememberCorrection:
    def test_a_correction_is_keyed_on_the_tax_number(self, user):
        invoice = make_invoice(user)

        rule = remember_correction(user, invoice, ExpenseCategory.MEALS)

        assert rule.match_type == CategoryRule.MatchType.SELLER_TAX_ID
        assert rule.match_value == "91310000MA1FL1AB2C"

    def test_it_falls_back_to_the_seller_name(self, user):
        invoice = make_invoice(user, seller_tax_id="")

        rule = remember_correction(user, invoice, ExpenseCategory.MEALS)

        assert rule.match_type == CategoryRule.MatchType.SELLER_NAME

    def test_correcting_twice_updates_one_rule(self, user):
        invoice = make_invoice(user)

        remember_correction(user, invoice, ExpenseCategory.MEALS)
        remember_correction(user, invoice, ExpenseCategory.OFFICE)

        assert CategoryRule.objects.count() == 1
        assert CategoryRule.objects.get().category == ExpenseCategory.OFFICE

    def test_an_invalid_category_is_not_remembered(self, user):
        invoice = make_invoice(user)

        assert remember_correction(user, invoice, "nonsense") is None
        assert CategoryRule.objects.count() == 0

    def test_an_invoice_with_nothing_to_key_on_teaches_nothing(self, user):
        invoice = make_invoice(
            user, seller_tax_id="", seller_name="", invoice_type=""
        )

        assert (
            remember_correction(user, invoice, ExpenseCategory.MEALS)
            is None
        )

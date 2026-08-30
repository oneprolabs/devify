"""Unit tests for export filename rendering."""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest

from expense.services import naming


pytestmark = pytest.mark.unit


def fake_invoice(**overrides):
    payload = {
        "uuid": "11111111-1111-1111-1111-111111111111",
        "issue_date": date(2026, 8, 12),
        "category": "transport_local",
        "seller_name": "滴滴出行",
        "total_amount": Decimal("128.50"),
        "invoice_no": "25117000000012345678",
        "invoice_type": "vat_electronic",
        "city": "上海",
        "buyer_name": "某公司",
        "email_attachment": SimpleNamespace(
            filename="invoice.pdf", file_path="/tmp/invoice.pdf"
        ),
        "source_file": None,
    }
    payload.update(overrides)
    return SimpleNamespace(**payload)


class TestSanitize:
    @pytest.mark.parametrize(
        "raw", ["a/b", "a\\b", "a:b", "a*b", "a?b", 'a"b', "a<b", "a>b", "a|b"]
    )
    def test_illegal_characters_are_replaced(self, raw):
        assert naming.sanitize(raw) == "a_b"

    def test_whitespace_collapses(self):
        assert naming.sanitize("a   b") == "a_b"

    def test_control_characters_are_replaced(self):
        assert naming.sanitize("a\x00b") == "a_b"


class TestRender:
    def test_default_template(self):
        name = naming.render(fake_invoice())
        assert name == (
            "20260812_市内交通_滴滴出行_128.50_25117000000012345678.pdf"
        )

    def test_missing_fields_leave_no_double_separator(self):
        # Non-standard tickets routinely carry no invoice number.
        name = naming.render(fake_invoice(invoice_no="", seller_name=""))
        assert "__" not in name
        assert name.startswith("20260812_市内交通_128.50")

    def test_a_long_seller_is_truncated(self):
        name = naming.render(fake_invoice(seller_name="很长的公司名称" * 10))
        assert len(name) <= naming.MAX_FILENAME_CHARS

    def test_the_whole_name_is_capped(self):
        name = naming.render(
            fake_invoice(invoice_no="9" * 200, seller_name="x" * 200)
        )
        assert len(name) <= naming.MAX_FILENAME_CHARS

    def test_the_original_extension_is_kept(self):
        invoice = fake_invoice(
            email_attachment=SimpleNamespace(
                filename="发票.ofd", file_path="/tmp/a.ofd"
            )
        )
        assert naming.render(invoice).endswith(".ofd")

    def test_a_custom_template_is_honored(self):
        name = naming.render(fake_invoice(), "{city}-{invoice_no}")
        assert name == "上海-25117000000012345678.pdf"

    def test_an_unknown_placeholder_drops_out(self):
        name = naming.render(fake_invoice(), "{city}_{nonsense}")
        assert name == "上海.pdf"

    def test_collisions_get_a_suffix(self):
        taken = set()
        first = naming.render(fake_invoice(), taken=taken)
        second = naming.render(fake_invoice(), taken=taken)

        # A zip with two identical entries silently loses one of them.
        assert first != second
        assert second.endswith("-2.pdf")

    def test_the_category_label_does_not_follow_the_ui_language(self):
        # An archived file must keep its name forever, so the name cannot
        # depend on the viewer's language or on a translation catalog
        # appearing later.
        from django.utils import translation

        with translation.override("en"):
            english = naming.render(fake_invoice())
        with translation.override("zh-hans"):
            chinese = naming.render(fake_invoice())

        assert english == chinese
        assert "市内交通" in english

    def test_an_empty_render_falls_back_to_the_uuid(self):
        invoice = fake_invoice(
            issue_date=None,
            category="",
            seller_name="",
            total_amount=None,
            invoice_no="",
        )
        assert naming.render(invoice).startswith("11111111-")

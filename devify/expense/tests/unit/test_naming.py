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
        name = naming.render(fake_invoice(), index=1)
        assert name == "1_20260812_市内交通_滴滴出行_128.50.pdf"

    def test_the_number_is_left_out_when_there_is_no_position(self):
        # Rendering outside an export has nothing to number.
        name = naming.render(fake_invoice())
        assert name == "20260812_市内交通_滴滴出行_128.50.pdf"

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


class TestFieldPicker:
    """
    The picker writes the template, so the two must agree.

    Seller and amount are not offered as choices: a name missing either
    cannot be told apart from the next file in the same claim.
    """

    def test_a_field_order_becomes_a_template(self):
        template = naming.template_from_fields(
            ["index", "category", "amount", "seller"]
        )
        assert template == "{index}_{category}_{amount}_{seller}"

    def test_required_fields_are_put_back(self):
        template = naming.template_from_fields(["index", "category"])
        assert "{seller}" in template
        assert "{amount}" in template

    def test_unknown_fields_are_dropped(self):
        template = naming.template_from_fields(["index", "nonsense"])
        assert "nonsense" not in template

    def test_a_template_reads_back_as_its_fields(self):
        fields = ["index", "category", "seller", "amount"]
        assert (
            naming.fields_from_template(naming.template_from_fields(fields))
            == fields
        )

    def test_the_default_round_trips(self):
        assert naming.template_from_fields(
            naming.fields_from_template(naming.DEFAULT_TEMPLATE)
        ) == naming.DEFAULT_TEMPLATE

    def test_a_hand_written_template_still_loads(self):
        assert naming.fields_from_template("{city}-{invoice_no}") == [
            "city",
            "invoice_no",
        ]


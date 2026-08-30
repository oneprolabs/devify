"""API tests for the invoice list, detail and correction endpoints."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from expense.constants import ExpenseCategory
from expense.models import CategoryRule, Invoice
from threadline.models import EmailAttachment, EmailMessage


pytestmark = [pytest.mark.integration, pytest.mark.django_db]

LIST_URL = "/api/v1/apps/expense/invoices"


def make_email(user, counter=[0]):
    counter[0] += 1
    return EmailMessage.objects.create(
        user=user,
        message_id=f"email_inv_{counter[0]:04d}",
        subject="您的发票",
        sender="billing@example.com",
        recipients="user@example.com",
        received_at=timezone.now() - timedelta(hours=1),
    )


def make_invoice(user, **overrides):
    email = overrides.pop("email", None) or make_email(user)
    payload = {
        "user": user,
        "email_message": email,
        "status": Invoice.Status.EXTRACTED,
        "invoice_type": "vat_electronic",
        "invoice_no": "25117000000012345678",
        "issue_date": date(2026, 8, 12),
        "seller_name": "滴滴出行",
        "seller_tax_id": "91110108MA002XY31Z",
        "total_amount": Decimal("128.50"),
        "category": ExpenseCategory.TRANSPORT_LOCAL,
        "city": "上海",
    }
    payload.update(overrides)
    return Invoice.objects.create(**payload)


class TestInvoiceList:
    def test_requires_authentication(self, api_client):
        assert api_client.get(LIST_URL).status_code in (401, 403)

    def test_only_own_invoices_are_listed(self, api_client, user, other_user):
        make_invoice(user)
        make_invoice(other_user)
        api_client.force_authenticate(user=user)

        response = api_client.get(LIST_URL)

        assert len(response.data["data"]) == 1

    def test_noise_is_hidden_by_default(self, api_client, user):
        make_invoice(user)
        make_invoice(user, status=Invoice.Status.NOT_INVOICE)
        make_invoice(user, status=Invoice.Status.FAILED)
        api_client.force_authenticate(user=user)

        response = api_client.get(LIST_URL)

        assert len(response.data["data"]) == 1

    def test_noise_is_reachable_with_an_explicit_filter(
        self, api_client, user
    ):
        make_invoice(user, status=Invoice.Status.FAILED)
        api_client.force_authenticate(user=user)

        response = api_client.get(f"{LIST_URL}?status=failed")

        assert len(response.data["data"]) == 1

    def test_category_filter(self, api_client, user):
        make_invoice(user)
        make_invoice(user, category=ExpenseCategory.MEALS)
        api_client.force_authenticate(user=user)

        response = api_client.get(f"{LIST_URL}?category=meals")

        assert len(response.data["data"]) == 1

    def test_date_range_filter(self, api_client, user):
        make_invoice(user, issue_date=date(2026, 1, 5))
        make_invoice(user, issue_date=date(2026, 8, 12))
        api_client.force_authenticate(user=user)

        response = api_client.get(f"{LIST_URL}?start=2026-06-01")

        assert len(response.data["data"]) == 1

    def test_keyword_search_covers_seller_and_number(self, api_client, user):
        make_invoice(user, seller_name="滴滴出行")
        make_invoice(user, seller_name="某酒店", invoice_no="999")
        api_client.force_authenticate(user=user)

        assert len(api_client.get(f"{LIST_URL}?q=滴滴").data["data"]) == 1
        assert len(api_client.get(f"{LIST_URL}?q=999").data["data"]) == 1

    def test_needs_review_filter(self, api_client, user):
        make_invoice(user)
        make_invoice(user, needs_review=True)
        api_client.force_authenticate(user=user)

        response = api_client.get(f"{LIST_URL}?needs_review=true")

        assert len(response.data["data"]) == 1


class TestInvoiceDetail:
    def test_detail_includes_provenance(self, api_client, user):
        email = make_email(user)
        attachment = EmailAttachment.objects.create(
            user=user,
            email_message=email,
            filename="发票.pdf",
            safe_filename="invoice.pdf",
            content_type="application/pdf",
            file_size=1000,
            file_path="/tmp/invoice.pdf",
            content_md5="a" * 32,
        )
        invoice = make_invoice(user, email=email, email_attachment=attachment)
        api_client.force_authenticate(user=user)

        data = api_client.get(f"{LIST_URL}/{invoice.uuid}").data["data"]

        assert data["filename"] == "发票.pdf"
        assert data["email_subject"] == "您的发票"

    def test_another_users_invoice_is_not_found(
        self, api_client, user, other_user
    ):
        invoice = make_invoice(other_user)
        api_client.force_authenticate(user=user)

        assert api_client.get(f"{LIST_URL}/{invoice.uuid}").status_code == 404

    def test_fields_can_be_corrected(self, api_client, user):
        invoice = make_invoice(user)
        api_client.force_authenticate(user=user)

        response = api_client.patch(
            f"{LIST_URL}/{invoice.uuid}",
            {"seller_name": "滴滴出行科技有限公司", "total_amount": "130.00"},
            format="json",
        )

        invoice.refresh_from_db()
        assert response.status_code == 200
        assert invoice.seller_name == "滴滴出行科技有限公司"
        assert invoice.total_amount == Decimal("130.00")

    def test_status_cannot_be_edited_by_hand(self, api_client, user):
        invoice = make_invoice(user)
        api_client.force_authenticate(user=user)

        api_client.patch(
            f"{LIST_URL}/{invoice.uuid}",
            {"status": Invoice.Status.NOT_INVOICE},
            format="json",
        )

        invoice.refresh_from_db()
        assert invoice.status == Invoice.Status.EXTRACTED

    def test_a_negative_amount_is_rejected(self, api_client, user):
        invoice = make_invoice(user)
        api_client.force_authenticate(user=user)

        response = api_client.patch(
            f"{LIST_URL}/{invoice.uuid}",
            {"total_amount": "-5.00"},
            format="json",
        )

        assert response.status_code == 400

    def test_an_invoice_can_be_deleted(self, api_client, user):
        invoice = make_invoice(user)
        api_client.force_authenticate(user=user)

        api_client.delete(f"{LIST_URL}/{invoice.uuid}")

        assert not Invoice.objects.filter(uuid=invoice.uuid).exists()


class TestCategoryCorrection:
    def test_correcting_a_category_teaches_a_rule(self, api_client, user):
        invoice = make_invoice(user)
        api_client.force_authenticate(user=user)

        api_client.patch(
            f"{LIST_URL}/{invoice.uuid}",
            {"category": ExpenseCategory.MEALS},
            format="json",
        )

        rule = CategoryRule.objects.get(user=user)
        assert rule.category == ExpenseCategory.MEALS
        assert rule.match_value == "91110108MA002XY31Z"

    def test_the_correction_is_marked_as_the_users_own(self, api_client, user):
        invoice = make_invoice(user)
        api_client.force_authenticate(user=user)

        api_client.patch(
            f"{LIST_URL}/{invoice.uuid}",
            {"category": ExpenseCategory.MEALS},
            format="json",
        )

        invoice.refresh_from_db()
        assert invoice.category_source == Invoice.CategorySource.USER

    def test_setting_the_same_category_teaches_nothing(self, api_client, user):
        invoice = make_invoice(user)
        api_client.force_authenticate(user=user)

        api_client.patch(
            f"{LIST_URL}/{invoice.uuid}",
            {"category": ExpenseCategory.TRANSPORT_LOCAL},
            format="json",
        )

        assert CategoryRule.objects.count() == 0

    def test_editing_other_fields_teaches_nothing(self, api_client, user):
        invoice = make_invoice(user)
        api_client.force_authenticate(user=user)

        api_client.patch(
            f"{LIST_URL}/{invoice.uuid}", {"city": "北京"}, format="json"
        )

        assert CategoryRule.objects.count() == 0


class TestInvoiceFile:
    def test_a_missing_original_is_reported(self, api_client, user):
        invoice = make_invoice(user)
        api_client.force_authenticate(user=user)

        response = api_client.get(f"{LIST_URL}/{invoice.uuid}/file")

        assert response.status_code == 404

    def test_the_original_is_served_to_its_owner(
        self, api_client, user, tmp_path
    ):
        target = tmp_path / "invoice.pdf"
        target.write_bytes(b"%PDF-1.4 body")
        email = make_email(user)
        attachment = EmailAttachment.objects.create(
            user=user,
            email_message=email,
            filename="invoice.pdf",
            safe_filename="invoice.pdf",
            content_type="application/pdf",
            file_size=13,
            file_path=str(target),
            content_md5="b" * 32,
        )
        invoice = make_invoice(user, email=email, email_attachment=attachment)
        api_client.force_authenticate(user=user)

        response = api_client.get(f"{LIST_URL}/{invoice.uuid}/file")

        assert response.status_code == 200

    def test_another_user_cannot_read_the_original(
        self, api_client, user, other_user, tmp_path
    ):
        # These files carry tax numbers and billing titles.
        target = tmp_path / "invoice.pdf"
        target.write_bytes(b"%PDF-1.4 body")
        email = make_email(other_user)
        attachment = EmailAttachment.objects.create(
            user=other_user,
            email_message=email,
            filename="invoice.pdf",
            safe_filename="invoice.pdf",
            content_type="application/pdf",
            file_size=13,
            file_path=str(target),
            content_md5="c" * 32,
        )
        invoice = make_invoice(
            other_user, email=email, email_attachment=attachment
        )
        api_client.force_authenticate(user=user)

        response = api_client.get(f"{LIST_URL}/{invoice.uuid}/file")

        assert response.status_code == 404

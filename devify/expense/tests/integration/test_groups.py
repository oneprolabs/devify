"""Integration tests for reimbursement groups, summaries and export."""

import zipfile
from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from expense.constants import ExpenseCategory
from expense.models import ExpenseGroup, ExpenseGroupItem, Invoice
from expense.services import export as export_service
from expense.services import groups as group_service
from threadline.models import EmailAttachment, EmailMessage


pytestmark = [pytest.mark.integration, pytest.mark.django_db]

GROUPS_URL = "/api/v1/apps/expense/groups"


def make_invoice(user, counter=[0], **overrides):
    counter[0] += 1
    email = EmailMessage.objects.create(
        user=user,
        message_id=f"email_grp_{counter[0]:04d}",
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
        "invoice_no": f"INV{counter[0]:08d}",
        "issue_date": date(2026, 8, 12),
        "seller_name": "滴滴出行",
        "total_amount": Decimal("100.00"),
        "tax_amount": Decimal("6.00"),
        "category": ExpenseCategory.TRANSPORT_LOCAL,
        "city": "上海",
    }
    payload.update(overrides)
    return Invoice.objects.create(**payload)


def attach_file(user, invoice, tmp_path, name="invoice.pdf"):
    target = tmp_path / f"{invoice.invoice_no}_{name}"
    target.write_bytes(b"%PDF-1.4 body")
    attachment = EmailAttachment.objects.create(
        user=user,
        email_message=invoice.email_message,
        filename=name,
        safe_filename=name,
        content_type="application/pdf",
        file_size=13,
        file_path=str(target),
        content_md5=f"{invoice.id:032d}",
    )
    invoice.email_attachment = attachment
    invoice.save(update_fields=["email_attachment"])
    return attachment


def make_group(user, name="八月报销"):
    return ExpenseGroup.objects.create(user=user, name=name)


class TestMembership:
    def test_adding_invoices_updates_the_totals(self, user):
        group = make_group(user)
        first = make_invoice(user)
        second = make_invoice(user, total_amount=Decimal("28.50"))

        group_service.add_invoices(
            group, [str(first.uuid), str(second.uuid)]
        )
        group.refresh_from_db()

        assert group.invoice_count == 2
        assert group.total_amount == Decimal("128.50")
        assert group.tax_amount == Decimal("12.00")

    def test_the_period_covers_the_invoice_dates(self, user):
        group = make_group(user)
        make_invoice(user, issue_date=date(2026, 8, 1))
        early = Invoice.objects.first()
        late = make_invoice(user, issue_date=date(2026, 8, 20))

        group_service.add_invoices(group, [str(early.uuid), str(late.uuid)])
        group.refresh_from_db()

        assert group.period_start == date(2026, 8, 1)
        assert group.period_end == date(2026, 8, 20)

    def test_adding_the_same_invoice_twice_is_harmless(self, user):
        group = make_group(user)
        invoice = make_invoice(user)

        group_service.add_invoices(group, [str(invoice.uuid)])
        group_service.add_invoices(group, [str(invoice.uuid)])
        group.refresh_from_db()

        assert group.invoice_count == 1

    def test_an_invoice_cannot_be_claimed_by_two_live_groups(self, user):
        # Claiming the same expense twice is the one mistake this feature
        # must never help a user make.
        first = make_group(user, "第一组")
        second = make_group(user, "第二组")
        invoice = make_invoice(user)
        group_service.add_invoices(first, [str(invoice.uuid)])

        with pytest.raises(group_service.GroupError):
            group_service.add_invoices(second, [str(invoice.uuid)])

    def test_an_archived_group_releases_its_invoices(self, user):
        first = make_group(user, "旧组")
        invoice = make_invoice(user)
        group_service.add_invoices(first, [str(invoice.uuid)])
        first.status = ExpenseGroup.Status.ARCHIVED
        first.save(update_fields=["status"])

        second = make_group(user, "新组")
        group_service.add_invoices(second, [str(invoice.uuid)])

        assert second.invoice_count == 1

    def test_a_duplicate_invoice_cannot_be_claimed(self, user):
        group = make_group(user)
        invoice = make_invoice(user, status=Invoice.Status.DUPLICATE)

        with pytest.raises(group_service.GroupError):
            group_service.add_invoices(group, [str(invoice.uuid)])

    def test_an_unknown_invoice_is_rejected(self, user):
        group = make_group(user)

        with pytest.raises(group_service.GroupError):
            group_service.add_invoices(
                group, ["11111111-1111-1111-1111-111111111111"]
            )

    def test_another_users_invoice_is_not_claimable(self, user, other_user):
        group = make_group(user)
        theirs = make_invoice(other_user)

        with pytest.raises(group_service.GroupError):
            group_service.add_invoices(group, [str(theirs.uuid)])

    def test_removing_an_invoice_updates_the_totals(self, user):
        group = make_group(user)
        invoice = make_invoice(user)
        group_service.add_invoices(group, [str(invoice.uuid)])

        group_service.remove_invoices(group, [str(invoice.uuid)])
        group.refresh_from_db()

        assert group.invoice_count == 0
        assert group.total_amount == Decimal("0")
        assert not ExpenseGroupItem.objects.exists()


class TestSummary:
    def test_summary_carries_the_capitalized_total(self, user):
        group = make_group(user)
        make_invoice(user, total_amount=Decimal("128.50"))
        invoice = Invoice.objects.first()
        group_service.add_invoices(group, [str(invoice.uuid)])

        summary = group_service.build_summary(group)

        assert summary["total_amount"] == "128.50"
        assert summary["total_amount_cn"] == "壹佰贰拾捌元伍角整"

    def test_breakdown_groups_by_category(self, user):
        group = make_group(user)
        first = make_invoice(user)
        second = make_invoice(
            user,
            category=ExpenseCategory.MEALS,
            total_amount=Decimal("50.00"),
        )
        group_service.add_invoices(
            group, [str(first.uuid), str(second.uuid)]
        )

        summary = group_service.build_summary(group)

        assert len(summary["category_breakdown"]) == 2
        assert summary["category_breakdown"][0]["amount"] == "100.00"

    def test_the_text_block_is_pasteable(self, user):
        group = make_group(user)
        group.purpose = "八月市内交通"
        group.save(update_fields=["purpose"])
        invoice = make_invoice(user)
        group_service.add_invoices(group, [str(invoice.uuid)])

        text = group_service.build_summary(group)["text_block"]

        assert "报销事由：八月市内交通" in text
        assert "金额大写：壹佰元整" in text
        assert invoice.invoice_no in text

    def test_an_empty_group_summarizes_to_zero(self, user):
        summary = group_service.build_summary(make_group(user))

        assert summary["invoice_count"] == 0
        assert summary["total_amount_cn"] == "零元整"


class TestExport:
    def test_the_archive_contains_the_files_and_a_manifest(
        self, user, tmp_path
    ):
        group = make_group(user)
        invoice = make_invoice(user)
        attach_file(user, invoice, tmp_path)
        group_service.add_invoices(group, [str(invoice.uuid)])

        archive_path = export_service.write_archive(group)

        with zipfile.ZipFile(archive_path) as archive:
            names = archive.namelist()
            manifest = archive.read("manifest.csv").decode("utf-8-sig")

        assert "manifest.csv" in names
        assert any(name.endswith(".pdf") for name in names)
        assert invoice.invoice_no in manifest

    def test_files_are_foldered_by_category(self, user, tmp_path):
        group = make_group(user)
        invoice = make_invoice(user)
        attach_file(user, invoice, tmp_path)
        group_service.add_invoices(group, [str(invoice.uuid)])

        archive_path = export_service.write_archive(group)

        with zipfile.ZipFile(archive_path) as archive:
            entries = [n for n in archive.namelist() if n != "manifest.csv"]

        assert entries[0].startswith("市内交通/")

    def test_a_flat_archive_has_no_folders(self, user, tmp_path):
        group = make_group(user)
        invoice = make_invoice(user)
        attach_file(user, invoice, tmp_path)
        group_service.add_invoices(group, [str(invoice.uuid)])

        archive_path = export_service.write_archive(group, by_category=False)

        with zipfile.ZipFile(archive_path) as archive:
            entries = [n for n in archive.namelist() if n != "manifest.csv"]

        assert "/" not in entries[0]

    def test_the_manifest_opens_cleanly_in_excel(self, user, tmp_path):
        # Without a BOM, Excel on Windows mangles Chinese seller names.
        group = make_group(user)
        invoice = make_invoice(user)
        attach_file(user, invoice, tmp_path)
        group_service.add_invoices(group, [str(invoice.uuid)])

        archive_path = export_service.write_archive(group)

        with zipfile.ZipFile(archive_path) as archive:
            raw = archive.read("manifest.csv")

        assert raw.startswith(b"\xef\xbb\xbf")

    def test_a_missing_original_is_counted_not_fatal(self, user):
        group = make_group(user)
        invoice = make_invoice(user)
        group_service.add_invoices(group, [str(invoice.uuid)])

        plan = export_service.plan_export(group)

        assert plan["missing_files"] == 1

    def test_an_empty_group_cannot_be_exported(self, user):
        with pytest.raises(export_service.ExportError):
            export_service.plan_export(make_group(user))


class TestGroupAPI:
    def test_groups_are_scoped_to_their_owner(
        self, api_client, user, other_user
    ):
        make_group(user, "我的")
        make_group(other_user, "别人的")
        api_client.force_authenticate(user=user)

        response = api_client.get(GROUPS_URL)

        assert len(response.data["data"]) == 1

    def test_a_group_can_be_created(self, api_client, user):
        api_client.force_authenticate(user=user)

        response = api_client.post(
            GROUPS_URL, {"name": "八月报销"}, format="json"
        )

        assert response.status_code == 201
        assert ExpenseGroup.objects.filter(user=user).count() == 1

    def test_a_duplicate_name_is_refused(self, api_client, user):
        make_group(user, "八月报销")
        api_client.force_authenticate(user=user)

        response = api_client.post(
            GROUPS_URL, {"name": "八月报销"}, format="json"
        )

        assert response.status_code == 400

    def test_double_claiming_is_refused_through_the_api(
        self, api_client, user
    ):
        first = make_group(user, "第一组")
        second = make_group(user, "第二组")
        invoice = make_invoice(user)
        group_service.add_invoices(first, [str(invoice.uuid)])
        api_client.force_authenticate(user=user)

        response = api_client.post(
            f"{GROUPS_URL}/{second.uuid}/items",
            {"invoice_uuids": [str(invoice.uuid)]},
            format="json",
        )

        assert response.status_code == 400

    def test_the_summary_endpoint_returns_pasteable_text(
        self, api_client, user
    ):
        group = make_group(user)
        invoice = make_invoice(user)
        group_service.add_invoices(group, [str(invoice.uuid)])
        api_client.force_authenticate(user=user)

        response = api_client.get(f"{GROUPS_URL}/{group.uuid}/summary")
        data = response.data["data"]

        assert "text_block" in data
        assert data["total_amount_cn"] == "壹佰元整"

    def test_export_preview_lists_the_filenames(
        self, api_client, user, tmp_path
    ):
        group = make_group(user)
        invoice = make_invoice(user)
        attach_file(user, invoice, tmp_path)
        group_service.add_invoices(group, [str(invoice.uuid)])
        api_client.force_authenticate(user=user)

        data = api_client.get(
            f"{GROUPS_URL}/{group.uuid}/export?preview=true"
        ).data["data"]

        assert data["files"][0]["filename"].endswith(".pdf")

    def test_another_users_group_is_not_found(
        self, api_client, user, other_user
    ):
        group = make_group(other_user)
        api_client.force_authenticate(user=user)

        assert (
            api_client.get(f"{GROUPS_URL}/{group.uuid}").status_code == 404
        )

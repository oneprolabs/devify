"""
The lifecycle stages behind the status chips.

The stages have to be mutually exclusive: an invoice appears under exactly
one chip, and the counts add up to the total. Anything else and the chips
lie about how much work is left.
"""

from datetime import date
from decimal import Decimal

import pytest
from django.utils import timezone

from expense.constants import ExpenseCategory
from expense.models import ExpenseGroup, Invoice
from expense.services import groups as group_service
from expense.services import invoices as invoice_service
from expense.services.groups import add_invoices
from threadline.models import EmailMessage


pytestmark = [pytest.mark.integration, pytest.mark.django_db]

LIST_URL = "/api/v1/apps/expense/invoices"
FILE_URL = "/api/v1/apps/expense/invoices/file-away"


def make_invoice(user, counter=[0], **overrides):
    counter[0] += 1
    email = EmailMessage.objects.create(
        user=user,
        message_id=f"email_stage_{counter[0]:04d}",
        subject="发票",
        sender="billing@example.com",
        recipients="user@example.com",
        received_at=timezone.now(),
    )
    payload = {
        "user": user,
        "email_message": email,
        "status": Invoice.Status.EXTRACTED,
        "invoice_no": f"ST{counter[0]:06d}",
        "issue_date": date(2026, 8, 12),
        "expense_date": date(2026, 8, 12),
        "seller_name": "某供应商",
        "buyer_name": "北京万云博华科技中心",
        "buyer_tax_id": "91110105MA01UYHY0T",
        "total_amount": Decimal("100.00"),
        "category": ExpenseCategory.MEALS,
    }
    payload.update(overrides)
    return Invoice.objects.create(**payload)


def put_in_group(user, invoice, status=ExpenseGroup.Status.DRAFT):
    group = ExpenseGroup.objects.create(
        user=user, name=f"组-{invoice.invoice_no}"
    )
    add_invoices(group, [str(invoice.uuid)])
    if status != ExpenseGroup.Status.DRAFT:
        group.status = status
        group.save(update_fields=["status"])
    return group


class TestStages:
    def test_a_fresh_invoice_is_waiting_to_be_claimed(self, user):
        make_invoice(user)

        counts = invoice_service.stage_counts(user)

        assert counts["todo"] == 1
        assert counts["claiming"] == 0

    def test_an_invoice_in_a_draft_group_is_in_flight(self, user):
        put_in_group(user, make_invoice(user))

        counts = invoice_service.stage_counts(user)

        assert counts["todo"] == 0
        assert counts["claiming"] == 1

    def test_a_reimbursed_group_moves_its_invoices_on(self, user):
        put_in_group(
            user, make_invoice(user), status=ExpenseGroup.Status.REIMBURSED
        )

        counts = invoice_service.stage_counts(user)

        assert counts["claiming"] == 0
        assert counts["reimbursed"] == 1

    def test_an_archived_group_releases_its_invoices(self, user):
        put_in_group(
            user, make_invoice(user), status=ExpenseGroup.Status.ARCHIVED
        )

        counts = invoice_service.stage_counts(user)

        assert counts["todo"] == 1

    def test_a_filed_invoice_leaves_the_queue(self, user):
        invoice = make_invoice(user)

        invoice_service.file_invoices(user, [str(invoice.uuid)], "personal")
        counts = invoice_service.stage_counts(user)

        assert counts["todo"] == 0
        assert counts["filed"] == 1

    def test_the_stages_partition_the_whole_set(self, user):
        make_invoice(user)
        put_in_group(user, make_invoice(user))
        put_in_group(
            user, make_invoice(user), status=ExpenseGroup.Status.REIMBURSED
        )
        filed = make_invoice(user)
        invoice_service.file_invoices(user, [str(filed.uuid)])

        counts = invoice_service.stage_counts(user)
        parts = (
            counts["todo"]
            + counts["claiming"]
            + counts["reimbursed"]
            + counts["filed"]
        )

        # Every invoice sits under exactly one chip.
        assert parts == counts["all"] == 4


class TestFiling:
    def test_filing_records_the_reason(self, user):
        invoice = make_invoice(user)

        invoice_service.file_invoices(user, [str(invoice.uuid)], "personal")
        invoice.refresh_from_db()

        assert invoice.disposition == Invoice.Disposition.FILED
        assert invoice.filed_reason == "personal"
        assert invoice.filed_at is not None

    def test_an_unknown_reason_falls_back(self, user):
        invoice = make_invoice(user)

        invoice_service.file_invoices(user, [str(invoice.uuid)], "nonsense")
        invoice.refresh_from_db()

        assert invoice.filed_reason == "other"

    def test_an_invoice_inside_a_group_cannot_be_filed(self, user):
        # It is already spoken for; filing it would contradict a claim in
        # progress.
        invoice = make_invoice(user)
        put_in_group(user, invoice)

        filed = invoice_service.file_invoices(user, [str(invoice.uuid)])
        invoice.refresh_from_db()

        assert filed == 0
        assert invoice.disposition == Invoice.Disposition.TO_CLAIM

    def test_filing_can_be_undone(self, user):
        invoice = make_invoice(user)
        invoice_service.file_invoices(user, [str(invoice.uuid)])

        restored = invoice_service.unfile_invoices(user, [str(invoice.uuid)])
        invoice.refresh_from_db()

        assert restored == 1
        assert invoice.disposition == Invoice.Disposition.TO_CLAIM
        assert invoice.filed_reason == ""

    def test_another_users_invoice_is_untouched(self, user, other_user):
        theirs = make_invoice(other_user)

        filed = invoice_service.file_invoices(user, [str(theirs.uuid)])
        theirs.refresh_from_db()

        assert filed == 0
        assert theirs.disposition == Invoice.Disposition.TO_CLAIM


class TestBuyerTitles:
    def test_titles_are_derived_from_real_invoices(self, user):
        make_invoice(user)
        make_invoice(user, buyer_name="孙琦", buyer_tax_id="")

        titles = invoice_service.buyer_titles(user)
        kinds = {row["name"]: row["kind"] for row in titles}

        assert kinds["北京万云博华科技中心"] == "company"
        assert kinds["孙琦"] == "personal"

    def test_counts_reflect_how_often_each_is_used(self, user):
        make_invoice(user)
        make_invoice(user)
        make_invoice(user, buyer_name="孙琦", buyer_tax_id="")

        titles = invoice_service.buyer_titles(user)

        assert titles[0]["name"] == "北京万云博华科技中心"
        assert titles[0]["count"] == 2


class TestStageAPI:
    def test_the_list_carries_counts_and_titles(self, api_client, user):
        make_invoice(user)
        api_client.force_authenticate(user=user)

        data = api_client.get(LIST_URL).data["data"]

        assert data["counts"]["todo"] == 1
        assert data["buyers"][0]["kind"] == "company"

    def test_the_stage_filter_narrows_the_list(self, api_client, user):
        make_invoice(user)
        put_in_group(user, make_invoice(user))
        api_client.force_authenticate(user=user)

        response = api_client.get(f"{LIST_URL}?stage=todo")
        rows = response.data["data"]["invoices"]

        assert len(rows) == 1

    def test_the_buyer_filter_narrows_the_list(self, api_client, user):
        make_invoice(user)
        make_invoice(user, buyer_name="孙琦", buyer_tax_id="")
        api_client.force_authenticate(user=user)

        rows = api_client.get(f"{LIST_URL}?buyer=孙琦").data["data"]["invoices"]

        assert len(rows) == 1

    def test_filing_through_the_api_returns_fresh_counts(
        self, api_client, user
    ):
        invoice = make_invoice(user)
        api_client.force_authenticate(user=user)

        response = api_client.post(
            FILE_URL,
            {"invoice_uuids": [str(invoice.uuid)], "reason": "personal"},
            format="json",
        )

        data = response.data["data"]
        assert data["filed"] == 1
        assert data["counts"]["filed"] == 1
        assert data["counts"]["todo"] == 0

    def test_restoring_through_the_api(self, api_client, user):
        invoice = make_invoice(user)
        invoice_service.file_invoices(user, [str(invoice.uuid)])
        api_client.force_authenticate(user=user)

        response = api_client.delete(
            FILE_URL, {"invoice_uuids": [str(invoice.uuid)]}, format="json"
        )

        assert response.data["data"]["restored"] == 1
        assert response.data["data"]["counts"]["todo"] == 1


class TestMovingBetweenGroups:
    def test_an_invoice_can_be_moved_to_another_group(self, user):
        invoice = make_invoice(user)
        source = put_in_group(user, invoice)
        target = ExpenseGroup.objects.create(user=user, name="八月出差")

        result = group_service.move_invoices(target, [str(invoice.uuid)])
        source.refresh_from_db()
        target.refresh_from_db()

        assert result["moved"] == 1
        assert result["from_groups"] == [source.name]
        assert target.invoice_count == 1
        assert source.invoice_count == 0

    def test_both_groups_totals_are_restated(self, user):
        invoice = make_invoice(user, total_amount=Decimal("250.00"))
        source = put_in_group(user, invoice)
        target = ExpenseGroup.objects.create(user=user, name="八月出差")

        group_service.move_invoices(target, [str(invoice.uuid)])
        source.refresh_from_db()
        target.refresh_from_db()

        assert target.total_amount == Decimal("250.00")
        assert source.total_amount == Decimal("0")

    def test_a_reimbursed_claim_cannot_be_rewritten(self, user):
        invoice = make_invoice(user)
        put_in_group(user, invoice, status=ExpenseGroup.Status.REIMBURSED)
        target = ExpenseGroup.objects.create(user=user, name="八月出差")

        with pytest.raises(group_service.GroupError):
            group_service.move_invoices(target, [str(invoice.uuid)])

    def test_moving_an_unclaimed_invoice_just_adds_it(self, user):
        invoice = make_invoice(user)
        target = ExpenseGroup.objects.create(user=user, name="八月出差")

        result = group_service.move_invoices(target, [str(invoice.uuid)])

        assert result["moved"] == 1
        assert result["from_groups"] == []

    def test_moving_into_the_group_it_is_already_in_is_harmless(self, user):
        invoice = make_invoice(user)
        group = put_in_group(user, invoice)

        result = group_service.move_invoices(group, [str(invoice.uuid)])
        group.refresh_from_db()

        assert result["moved"] == 0
        assert group.invoice_count == 1

    def test_a_filed_invoice_rejoins_the_claim_when_moved(self, user):
        invoice = make_invoice(user)
        invoice_service.file_invoices(user, [str(invoice.uuid)])
        target = ExpenseGroup.objects.create(user=user, name="八月出差")

        group_service.move_invoices(target, [str(invoice.uuid)])
        invoice.refresh_from_db()

        assert invoice.disposition == Invoice.Disposition.TO_CLAIM

    def test_the_api_moves_and_reports_the_old_group(self, api_client, user):
        invoice = make_invoice(user)
        source = put_in_group(user, invoice)
        target = ExpenseGroup.objects.create(user=user, name="八月出差")
        api_client.force_authenticate(user=user)

        response = api_client.put(
            f"/api/v1/apps/expense/groups/{target.uuid}/items",
            {"invoice_uuids": [str(invoice.uuid)]},
            format="json",
        )

        assert response.data["data"]["moved"] == 1
        assert response.data["data"]["from_groups"] == [source.name]

    def test_the_api_refuses_to_raid_a_settled_claim(self, api_client, user):
        invoice = make_invoice(user)
        put_in_group(user, invoice, status=ExpenseGroup.Status.REIMBURSED)
        target = ExpenseGroup.objects.create(user=user, name="八月出差")
        api_client.force_authenticate(user=user)

        response = api_client.put(
            f"/api/v1/apps/expense/groups/{target.uuid}/items",
            {"invoice_uuids": [str(invoice.uuid)]},
            format="json",
        )

        assert response.status_code == 400


class TestGroupSections:
    def test_invoices_are_split_by_category(self, user):
        group = ExpenseGroup.objects.create(user=user, name="八月出差")
        meal = make_invoice(user, category=ExpenseCategory.MEALS)
        taxi = make_invoice(user, category=ExpenseCategory.TRANSPORT_LOCAL)
        add_invoices(group, [str(meal.uuid), str(taxi.uuid)])

        sections = group_service.category_sections(
            group_service.group_invoices(group)
        )

        assert {row["category"] for row in sections} == {
            ExpenseCategory.MEALS,
            ExpenseCategory.TRANSPORT_LOCAL,
        }

    def test_each_section_carries_its_own_subtotal(self, user):
        group = ExpenseGroup.objects.create(user=user, name="八月出差")
        first = make_invoice(
            user, category=ExpenseCategory.MEALS, total_amount=Decimal("80.00")
        )
        second = make_invoice(
            user, category=ExpenseCategory.MEALS, total_amount=Decimal("40.00")
        )
        add_invoices(group, [str(first.uuid), str(second.uuid)])

        sections = group_service.category_sections(
            group_service.group_invoices(group)
        )

        assert sections[0]["count"] == 2
        assert sections[0]["amount"] == "120.00"

    def test_the_largest_category_comes_first(self, user):
        group = ExpenseGroup.objects.create(user=user, name="八月出差")
        small = make_invoice(
            user, category=ExpenseCategory.MEALS, total_amount=Decimal("30.00")
        )
        large = make_invoice(
            user,
            category=ExpenseCategory.ACCOMMODATION,
            total_amount=Decimal("900.00"),
        )
        add_invoices(group, [str(small.uuid), str(large.uuid)])

        sections = group_service.category_sections(
            group_service.group_invoices(group)
        )

        assert sections[0]["category"] == ExpenseCategory.ACCOMMODATION

    def test_the_sections_hold_every_invoice(self, user):
        group = ExpenseGroup.objects.create(user=user, name="八月出差")
        uuids = [str(make_invoice(user).uuid) for _ in range(3)]
        add_invoices(group, uuids)

        sections = group_service.category_sections(
            group_service.group_invoices(group)
        )

        assert sum(row["count"] for row in sections) == 3

    def test_the_detail_api_serves_the_sections(self, api_client, user):
        group = ExpenseGroup.objects.create(user=user, name="八月出差")
        meal = make_invoice(user, category=ExpenseCategory.MEALS)
        add_invoices(group, [str(meal.uuid)])
        api_client.force_authenticate(user=user)

        response = api_client.get(
            f"/api/v1/apps/expense/groups/{group.uuid}"
        )

        section = response.data["data"]["sections"][0]
        assert section["label"] == "餐饮"
        assert section["invoices"][0]["invoice_no"] == meal.invoice_no

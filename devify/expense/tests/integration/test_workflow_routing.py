"""
Routing an invoice email inside the email workflow.

An invoice notification is a document delivery, not a conversation. These
assert the two things that make routing safe: the rule is strict enough
that ordinary mail is never diverted, and a wrong guess costs nothing
because the workflow falls back on the same single charge.
"""

from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.utils import timezone

from billing.models import EmailCreditsTransaction, UserCredits
from billing.services.credits_service import CreditsService
from expense.models import Invoice
from expense.services.config_service import get_user_config
from expense.services.routing import should_route_to_invoices
from threadline.agents.nodes.invoice_node import (
    InvoiceNode,
    route_after_invoice,
)
from threadline.models import EmailAttachment, EmailMessage


pytestmark = [pytest.mark.integration, pytest.mark.django_db]

RECOGNIZE_PATH = "expense.services.recognition.recognize_email"


def enable_expense(user):
    config = get_user_config(user)
    config.enabled = True
    config.enabled_at = timezone.now()
    config.save()
    return config


def make_email(user, subject="您的电子发票", body="", counter=[0]):
    counter[0] += 1
    return EmailMessage.objects.create(
        user=user,
        message_id=f"email_route_{counter[0]:04d}",
        subject=subject,
        sender="billing@example.com",
        recipients="user@example.com",
        text_content=body,
        received_at=timezone.now() - timedelta(hours=1),
    )


def attach(user, email, filename="document.pdf", counter=[0]):
    counter[0] += 1
    return EmailAttachment.objects.create(
        user=user,
        email_message=email,
        filename=filename,
        safe_filename=filename,
        content_type="application/pdf",
        file_size=120_000,
        file_path=f"/tmp/{filename}",
        content_md5=f"route{counter[0]:027d}",
    )


def give_credits(user, amount):
    CreditsService.get_user_credits(user.id)
    credits = UserCredits.objects.get(user_id=user.id, is_active=True)
    credits.base_credits = amount
    credits.consumed_credits = 0
    credits.save(update_fields=["base_credits", "consumed_credits"])
    return credits


class TestRoutingRule:
    def test_a_keyword_in_the_subject_routes(self, user):
        enable_expense(user)
        email = make_email(user, subject="【电子发票】北京麻六记")
        attach(user, email)

        assert should_route_to_invoices(email) is True

    def test_a_keyword_only_in_the_body_does_not(self, user):
        # This is the case that matters: across a real mailbox every phone
        # bill and usage report mentioning 发票 in a footer matched the
        # scan filter. Routing those would cost each one its summary.
        enable_expense(user)
        email = make_email(
            user,
            subject="【北京移动】您的话费账单已送达",
            body="点击查看账单 https://example.com/bill 如需发票请登录",
        )
        attach(user, email)

        assert should_route_to_invoices(email) is False

    def test_a_keyword_in_the_filename_routes(self, user):
        enable_expense(user)
        email = make_email(user, subject="转发：上月费用")
        attach(user, email, filename="电子发票_209.20元.pdf")

        assert should_route_to_invoices(email) is True

    def test_a_link_delivered_invoice_still_routes(self, user):
        # 12306 and its kind send a download link rather than a file, and
        # requiring an attachment would lose them.
        enable_expense(user)
        email = make_email(
            user,
            subject="网上购票系统-电子发票通知",
            body="下载地址 https://example.com/fapiao/9f2c",
        )

        assert should_route_to_invoices(email) is True

    def test_nothing_to_read_does_not_route(self, user):
        enable_expense(user)
        email = make_email(user, subject="您的电子发票")

        assert should_route_to_invoices(email) is False

    def test_the_app_being_off_does_not_route(self, user):
        email = make_email(user, subject="【电子发票】北京麻六记")
        attach(user, email)

        assert should_route_to_invoices(email) is False


class TestRouteAfterInvoice:
    def test_invoices_found_ends_the_workflow(self):
        assert route_after_invoice({"invoice_count": 2}) == "workflow_finalize"

    def test_nothing_found_continues_normally(self):
        assert route_after_invoice({"invoice_count": 0}) == "image_intent"

    def test_a_missing_count_continues_normally(self):
        # Every way this can go wrong leaves the count unset, so the
        # fallback needs no separate error path.
        assert route_after_invoice({}) == "image_intent"


class TestInvoiceNode:
    def _state(self, email):
        return {"id": str(email.id), "user_id": str(email.user_id)}

    def test_it_recognizes_without_charging_again(self, user):
        # The workflow already charged for this email; charging here would
        # make an invoice email cost double, which is the whole point.
        enable_expense(user)
        give_credits(user, 10)
        email = make_email(user, subject="【电子发票】北京麻六记")
        attach(user, email)

        with patch(RECOGNIZE_PATH) as recognize:
            recognize.return_value = {"extracted": 1}
            InvoiceNode().execute_processing(self._state(email))

        assert recognize.call_args.kwargs["bill"] is False

    def test_no_credit_is_spent_on_the_invoice_path(self, user):
        enable_expense(user)
        give_credits(user, 10)
        email = make_email(user, subject="【电子发票】北京麻六记")
        attach(user, email)
        Invoice.objects.create(
            user=user,
            email_message=email,
            status=Invoice.Status.EXTRACTED,
            invoice_no="ROUTE-1",
            seller_name="北京麻六记",
            total_amount=Decimal("209.20"),
            issue_date=timezone.now().date(),
            expense_date=timezone.now().date(),
        )

        with patch(RECOGNIZE_PATH, return_value={"extracted": 1}):
            InvoiceNode().execute_processing(self._state(email))

        assert EmailCreditsTransaction.objects.filter(
            email_message_id=email.id
        ).count() == 0

    def test_the_summary_states_the_facts(self, user):
        enable_expense(user)
        email = make_email(user, subject="【电子发票】北京麻六记")
        attach(user, email)
        Invoice.objects.create(
            user=user,
            email_message=email,
            status=Invoice.Status.EXTRACTED,
            invoice_no="ROUTE-2",
            seller_name="北京麻六记餐饮管理有限公司",
            total_amount=Decimal("209.20"),
            issue_date=timezone.now().date(),
            expense_date=timezone.now().date(),
        )

        with patch(RECOGNIZE_PATH, return_value={"extracted": 1}):
            state = InvoiceNode().execute_processing(self._state(email))

        assert state["invoice_count"] == 1
        assert "北京麻六记餐饮管理有限公司" in state["summary_content"]
        assert "209.20" in state["summary_content"]

    def test_a_wrong_guess_falls_back(self, user):
        # It looked like an invoice email and held none. The state must
        # stay untouched so the normal pipeline picks it up.
        enable_expense(user)
        email = make_email(user, subject="【电子发票】相关的合同")
        attach(user, email, filename="contract.pdf")

        with patch(RECOGNIZE_PATH, return_value={"extracted": 0}):
            state = InvoiceNode().execute_processing(self._state(email))

        assert state["invoice_count"] == 0
        assert state.get("summary_title") is None

    def test_an_ordinary_email_is_never_read_as_invoices(self, user):
        enable_expense(user)
        email = make_email(user, subject="周会纪要", body="发票的事下周说")
        attach(user, email)

        with patch(RECOGNIZE_PATH) as recognize:
            state = InvoiceNode().execute_processing(self._state(email))

        recognize.assert_not_called()
        assert state["invoice_count"] == 0

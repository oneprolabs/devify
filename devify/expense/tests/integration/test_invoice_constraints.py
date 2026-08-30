"""
Database-level guards for invoice uniqueness.

These assert the constraints are enforced by MariaDB rather than only
declared in Python: Django silently skips ``UniqueConstraint`` with a
``condition`` on MySQL/MariaDB, which would leave deduplication resting on
an index that does not exist.
"""

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from expense.models import Invoice
from threadline.models import EmailAttachment, EmailMessage


pytestmark = [pytest.mark.integration, pytest.mark.django_db]


def _make_email(user, message_id="email_test_0001"):
    return EmailMessage.objects.create(
        user=user,
        message_id=message_id,
        subject="Invoice",
        sender="billing@example.com",
        recipients="user@example.com",
        received_at=timezone.now(),
    )


def _make_attachment(user, email, filename="invoice.pdf"):
    return EmailAttachment.objects.create(
        user=user,
        email_message=email,
        filename=filename,
        safe_filename=filename,
        content_type="application/pdf",
        file_size=1024,
        file_path=f"/tmp/{filename}",
        content_md5="0" * 32,
    )


class TestDedupKeyConstraint:
    def test_same_dedup_key_for_one_user_is_rejected(self, user):
        email = _make_email(user)
        Invoice.objects.create(
            user=user, email_message=email, dedup_key="INV-1"
        )

        with pytest.raises(IntegrityError):
            with transaction.atomic():
                Invoice.objects.create(
                    user=user, email_message=email, dedup_key="INV-1"
                )

    def test_same_dedup_key_across_users_is_allowed(self, user, other_user):
        email = _make_email(user)
        other_email = _make_email(other_user, message_id="email_test_0002")

        Invoice.objects.create(
            user=user, email_message=email, dedup_key="INV-1"
        )
        Invoice.objects.create(
            user=other_user, email_message=other_email, dedup_key="INV-1"
        )

        assert Invoice.objects.filter(dedup_key="INV-1").count() == 2

    def test_rows_without_a_dedup_key_do_not_collide(self, user):
        # Not-yet-extracted invoices carry NULL, and NULLs never collide in
        # a MySQL unique index. An empty string would have collided.
        email = _make_email(user)

        Invoice.objects.create(user=user, email_message=email)
        Invoice.objects.create(user=user, email_message=email)

        assert Invoice.objects.filter(dedup_key__isnull=True).count() == 2


class TestAttachmentConstraint:
    def test_one_attachment_yields_at_most_one_invoice(self, user):
        email = _make_email(user)
        attachment = _make_attachment(user, email)
        Invoice.objects.create(
            user=user, email_message=email, email_attachment=attachment
        )

        with pytest.raises(IntegrityError):
            with transaction.atomic():
                Invoice.objects.create(
                    user=user, email_message=email, email_attachment=attachment
                )

    def test_invoices_without_an_attachment_do_not_collide(self, user):
        email = _make_email(user)

        Invoice.objects.create(
            user=user,
            email_message=email,
            source_type=Invoice.SourceType.BODY_LINK,
        )
        Invoice.objects.create(
            user=user,
            email_message=email,
            source_type=Invoice.SourceType.BODY_LINK,
        )

        assert (
            Invoice.objects.filter(email_attachment__isnull=True).count() == 2
        )

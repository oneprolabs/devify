"""
Seed the expense date for invoices recognized before the field existed.

The issue date is the only thing on record for them, which is also the
fallback the extractor uses when a document carries no travel date.
"""

from django.db import migrations, models


def forwards(apps, schema_editor):
    Invoice = apps.get_model("expense", "Invoice")
    Invoice.objects.filter(expense_date__isnull=True).update(
        expense_date=models.F("issue_date")
    )


def backwards(apps, schema_editor):
    Invoice = apps.get_model("expense", "Invoice")
    Invoice.objects.update(expense_date=None)


class Migration(migrations.Migration):

    dependencies = [
        ("expense", "0003_invoice_expense_date_and_more"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]

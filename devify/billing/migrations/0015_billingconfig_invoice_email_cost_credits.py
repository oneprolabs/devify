from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("billing", "0014_alter_plan_status_default"),
    ]

    operations = [
        migrations.AddField(
            model_name="billingconfig",
            name="invoice_email_cost_credits",
            field=models.IntegerField(default=1),
        ),
    ]

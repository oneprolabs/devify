from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0015_billingconfig_invoice_email_cost_credits'),
    ]

    operations = [
        migrations.AlterField(
            model_name='paymentprovider',
            name='name',
            field=models.CharField(help_text="e.g., 'platform', 'stripe', 'alipay', 'wechat'", max_length=50, unique=True),
        ),
    ]

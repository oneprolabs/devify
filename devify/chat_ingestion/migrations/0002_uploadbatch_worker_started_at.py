from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("chat_ingestion", "0001_initial")]

    operations = [
        migrations.AddField(
            model_name="uploadbatch",
            name="worker_started_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]

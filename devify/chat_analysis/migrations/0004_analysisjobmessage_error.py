from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("chat_analysis", "0003_scheduledanalysisrun"),
    ]

    operations = [
        migrations.AddField(
            model_name="analysisjobmessage",
            name="error",
            field=models.TextField(blank=True),
        ),
    ]

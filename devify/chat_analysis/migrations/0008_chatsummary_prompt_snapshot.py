from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("chat_analysis", "0007_summary_stale_index"),
    ]

    operations = [
        migrations.AddField(
            model_name="chatsummary",
            name="prompt_snapshot",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]

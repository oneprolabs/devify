from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("spaces", "0002_backfill_personal_spaces"),
    ]

    operations = [
        migrations.CreateModel(
            name="SpaceTakeover",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("reason", models.TextField(max_length=500)),
                ("active", models.BooleanField(default=True)),
                ("started_at", models.DateTimeField(auto_now_add=True)),
                ("ended_at", models.DateTimeField(blank=True, null=True)),
                ("admin", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="space_takeovers", to=settings.AUTH_USER_MODEL)),
                ("space", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="takeovers", to="spaces.space")),
            ],
            options={
                "indexes": [
                    models.Index(fields=["space", "active"], name="spaces_spac_space_i_4fbba1_idx"),
                    models.Index(fields=["admin", "active"], name="spaces_spac_admin_i_6ca7e2_idx"),
                ],
            },
        ),
    ]

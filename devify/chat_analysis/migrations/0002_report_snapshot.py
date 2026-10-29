import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("chat_analysis", "0001_initial"),
        ("spaces", "0003_spacetakeover"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ReportItem",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("position", models.PositiveIntegerField()),
                ("title", models.CharField(max_length=500)),
                ("summary", models.TextField()),
                ("label", models.TextField(blank=True)),
                ("time_text", models.TextField(blank=True)),
                ("contact_text", models.TextField(blank=True)),
                ("followup_text", models.TextField(blank=True)),
                ("followup_kind", models.CharField(blank=True, max_length=40)),
                ("display_kind", models.CharField(blank=True, max_length=80)),
            ],
            options={
                "ordering": ("position", "id"),
            },
        ),
        migrations.CreateModel(
            name="Report",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "uuid",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, unique=True
                    ),
                ),
                ("request_key", models.CharField(max_length=255)),
                ("title", models.CharField(max_length=500)),
                ("period_start", models.DateTimeField(blank=True, null=True)),
                ("period_end", models.DateTimeField(blank=True, null=True)),
                (
                    "body_format",
                    models.CharField(
                        choices=[("markdown", "Markdown"), ("html", "HTML")],
                        default="markdown",
                        max_length=20,
                    ),
                ),
                ("body", models.TextField(blank=True)),
                ("source_info", models.JSONField(blank=True, null=True)),
                ("content", models.JSONField(blank=True, null=True)),
                ("snapshot_ref", models.JSONField(blank=True, null=True)),
                ("processing", models.JSONField(blank=True, default=dict)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("queued", "Queued"),
                            ("ready", "Ready"),
                            ("partial", "Partial"),
                            ("failed", "Failed"),
                        ],
                        default="ready",
                        max_length=20,
                    ),
                ),
                ("generated_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="chat_reports",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "previous_report",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="next_reports",
                        to="chat_analysis.report",
                    ),
                ),
                (
                    "space",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="chat_reports",
                        to="spaces.space",
                    ),
                ),
            ],
            options={
                "ordering": ("-generated_at", "-id"),
            },
        ),
        migrations.CreateModel(
            name="ReportItemSource",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("reference_key", models.CharField(max_length=255)),
                (
                    "source_kind",
                    models.CharField(
                        choices=[
                            ("event", "Event"),
                            ("note", "Note"),
                            ("reference", "Reference"),
                        ],
                        max_length=20,
                    ),
                ),
                ("reference_url", models.URLField(blank=True)),
                ("display_text", models.TextField(blank=True)),
                ("event_snapshot", models.JSONField(blank=True, null=True)),
                ("note_snapshot", models.JSONField(blank=True, null=True)),
                (
                    "event",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="report_sources",
                        to="chat_analysis.event",
                    ),
                ),
                (
                    "item",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="sources",
                        to="chat_analysis.reportitem",
                    ),
                ),
                (
                    "note",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="report_sources",
                        to="chat_analysis.note",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="ReportSection",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("section_key", models.CharField(max_length=100)),
                ("title", models.CharField(max_length=500)),
                ("position", models.PositiveIntegerField()),
                (
                    "report",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="sections",
                        to="chat_analysis.report",
                    ),
                ),
            ],
            options={
                "ordering": ("position", "id"),
            },
        ),
        migrations.AddField(
            model_name="reportitem",
            name="section",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="items",
                to="chat_analysis.reportsection",
            ),
        ),
        migrations.AddIndex(
            model_name="report",
            index=models.Index(
                fields=["space", "period_start", "generated_at"],
                name="chat_analys_space_i_ef2408_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="report",
            index=models.Index(
                fields=["space", "status", "generated_at"],
                name="chat_analys_space_i_fde207_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="report",
            constraint=models.UniqueConstraint(
                fields=("space", "request_key"),
                name="unique_chat_report_request",
            ),
        ),
        migrations.AddConstraint(
            model_name="reportitemsource",
            constraint=models.UniqueConstraint(
                fields=("item", "reference_key"),
                name="unique_chat_report_item_source",
            ),
        ),
        migrations.AddConstraint(
            model_name="reportsection",
            constraint=models.UniqueConstraint(
                fields=("report", "section_key"),
                name="unique_chat_report_section_key",
            ),
        ),
        migrations.AddConstraint(
            model_name="reportsection",
            constraint=models.UniqueConstraint(
                fields=("report", "position"),
                name="unique_chat_report_section_position",
            ),
        ),
        migrations.AddConstraint(
            model_name="reportitem",
            constraint=models.UniqueConstraint(
                fields=("section", "position"),
                name="unique_chat_report_item_position",
            ),
        ),
    ]

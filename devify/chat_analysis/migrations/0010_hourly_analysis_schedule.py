"""Move only the former default event tick to the hourly schedule."""

from django.db import migrations
from django.utils import timezone


def use_hourly_tick(apps, schema_editor):
    periodic = apps.get_model("django_celery_beat", "PeriodicTask")
    crontab = apps.get_model("django_celery_beat", "CrontabSchedule")
    changes = apps.get_model("django_celery_beat", "PeriodicTasks")
    alias = schema_editor.connection.alias
    tasks = periodic.objects.using(alias).filter(
        name="chat-analysis-run-due-scheduled-analysis",
        task="chat_analysis.tasks.run_due_scheduled_analysis_task",
        interval__isnull=True,
        crontab__minute="*/5",
        crontab__hour="*",
        crontab__day_of_week="*",
        crontab__day_of_month="*",
        crontab__month_of_year="*",
    )
    for task in tasks.select_related("crontab"):
        values = {
            field: getattr(task.crontab, field)
            for field in (
                "hour",
                "day_of_week",
                "day_of_month",
                "month_of_year",
                "timezone",
            )
        }
        hourly = (
            crontab.objects.using(alias)
            .filter(
                minute="0",
                **values,
            )
            .first()
        )
        if hourly is None:
            hourly = crontab.objects.using(alias).create(minute="0", **values)
        periodic.objects.using(alias).filter(pk=task.pk).update(
            crontab_id=hourly.pk,
        )
        changes.objects.using(alias).update_or_create(
            ident=1,
            defaults={"last_update": timezone.now()},
        )


class Migration(migrations.Migration):
    dependencies = [
        ("chat_analysis", "0009_analysis_execution_slots"),
        ("django_celery_beat", "0019_alter_periodictasks_options"),
    ]
    operations = [
        migrations.RunPython(use_hourly_tick, migrations.RunPython.noop),
    ]

"""Normalise destination_city on rows written before the spelling was fixed."""

from django.db import migrations

# Kept local to the migration: it has to describe the world as it was when
# this ran, not follow later edits to the service.
CITY_SUFFIXES = ("特别行政区", "自治区", "省", "市")


def canonical(name: str) -> str:
    name = (name or "").strip()
    for suffix in CITY_SUFFIXES:
        if len(name) > len(suffix) + 1 and name.endswith(suffix):
            return name[: -len(suffix)]
    return name


def forwards(apps, schema_editor):
    """
    A suggestion's destination_city is matched exactly when deciding whether
    one has already been accepted or dismissed. It is written canonically
    now, so a row stored as 上海市 would never match the recomputed 上海 —
    and a trip the user dismissed would come back as a new suggestion.
    """
    TripSuggestion = apps.get_model("expense", "TripSuggestion")
    for row in TripSuggestion.objects.all().iterator():
        fixed = canonical(row.destination_city)
        if fixed != row.destination_city:
            row.destination_city = fixed
            row.save(update_fields=["destination_city"])


class Migration(migrations.Migration):

    dependencies = [
        ("expense", "0007_alter_expenseuserconfig_home_city"),
    ]

    operations = [
        # No reverse: the original spelling is not recoverable, and the
        # canonical one is valid under the old code too.
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]

"""The space UUID conversion must be repeatable and verifiable."""

import importlib

import pytest
from django.apps import apps as django_apps
from django.core.management import call_command
from django.db import connection

MIGRATION = importlib.import_module(
    "spaces.migrations.0002_space_uuid_primary_key"
)

pytestmark = pytest.mark.django_db(transaction=True)


def _column_types(table, column):
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT column_type FROM information_schema.columns "
            "WHERE table_schema = DATABASE() AND table_name = %s "
            "AND column_name = %s",
            [table, column],
        )
        row = cursor.fetchone()
    return row[0].lower() if row else None


def _table_exists(table):
    return table in set(connection.introspection.table_names())


def test_forwards_can_run_again_on_a_converted_schema():
    with connection.schema_editor() as editor:
        MIGRATION.forwards(django_apps, editor)

    expected = MIGRATION._uuid_db_type(connection)
    assert _column_types("spaces_space", "id") == expected
    assert not _table_exists(MIGRATION.REFS_TABLE)


def test_conversion_leaves_no_staged_columns_behind():
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT table_name, column_name "
            "FROM information_schema.columns "
            "WHERE table_schema = DATABASE()"
        )
        leftovers = [
            (table, column)
            for table, column in cursor.fetchall()
            if column.endswith(MIGRATION.TEMP_SUFFIX)
        ]
    assert leftovers == []


def test_mapping_table_keeps_integer_and_uuid_identifiers():
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = DATABASE() AND table_name = %s",
            [MIGRATION.MAPPING_TABLE],
        )
        columns = {row[0] for row in cursor.fetchall()}
    assert columns == {"old_id", "new_id", "migrated_at"}


def test_verify_command_accepts_the_migrated_schema(capsys):
    call_command("verify_space_uuid")
    output = capsys.readouterr().out
    assert "spaces_space.id" in output
    assert "OK" in output


def test_every_foreign_key_on_a_converted_table_survives():
    """Dropping a foreign key leaves its index behind; the constraint must
    still come back on every column, not only on ``space_id``."""
    converted = {
        model._meta.db_table for model, _ in MIGRATION._space_relations(
            django_apps
        )
    }
    checked = 0
    with connection.cursor() as cursor:
        tables = set(connection.introspection.table_names(cursor))
        for model in django_apps.get_models():
            table = model._meta.db_table
            if table not in tables or table not in converted:
                continue
            constraints = connection.introspection.get_constraints(
                cursor, table
            )
            referenced = {
                column
                for info in constraints.values()
                if info.get("foreign_key")
                for column in info.get("columns") or []
            }
            for field in model._meta.local_fields:
                remote = getattr(field, "remote_field", None)
                if field.concrete and remote is not None:
                    assert field.column in referenced, (
                        f"{table}.{field.column} lost its foreign key"
                    )
                    checked += 1
    assert checked > 0

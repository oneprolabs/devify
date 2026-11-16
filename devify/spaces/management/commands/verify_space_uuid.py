"""Verify that space identifiers and their relations are fully converted."""

from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.db import connection

MAPPING_TABLE = "spaces_space_id_map"
REFS_TABLE = "spaces_space_uuid_refs"
TEMP_SUFFIX = "__uuid_tmp"


def _quote(name):
    return connection.ops.quote_name(name)


def _uuid_db_type():
    if connection.features.has_native_uuid_field:
        return "uuid"
    return "char(32)"


def _space_relations():
    """Yield every concrete field that points at ``spaces.Space``."""
    for model in apps.get_models():
        if model._meta.label_lower == "spaces.space":
            continue
        for field in model._meta.local_fields:
            remote = getattr(field, "remote_field", None)
            if (
                field.concrete
                and remote is not None
                and remote.model._meta.label_lower == "spaces.space"
            ):
                yield model, field


def _column(table, column):
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT column_type, is_nullable "
            "FROM information_schema.columns "
            "WHERE table_schema = DATABASE() AND table_name = %s "
            "AND column_name = %s",
            [table, column],
        )
        return cursor.fetchone()


def _table_exists(table):
    return table in set(connection.introspection.table_names())


def _row_count(table):
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT COUNT(*) FROM {_quote(table)}")
        return cursor.fetchone()[0]


def _orphan_count(table, column):
    with connection.cursor() as cursor:
        cursor.execute(
            f"SELECT COUNT(*) FROM {_quote(table)} x "
            f"LEFT JOIN {_quote('spaces_space')} s "
            f"ON s.{_quote('id')} = x.{_quote(column)} "
            f"WHERE x.{_quote(column)} IS NOT NULL "
            f"AND s.{_quote('id')} IS NULL"
        )
        return cursor.fetchone()[0]


def _has_primary_key(table):
    with connection.cursor() as cursor:
        constraints = connection.introspection.get_constraints(cursor, table)
    return any(
        info.get("primary_key") for info in constraints.values()
    )


def _has_foreign_key(table, column):
    with connection.cursor() as cursor:
        constraints = connection.introspection.get_constraints(cursor, table)
    return any(
        info.get("foreign_key") and column in (info.get("columns") or [])
        for info in constraints.values()
    )


def _temp_columns():
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT table_name, column_name FROM information_schema.columns "
            "WHERE table_schema = DATABASE()"
        )
        return [
            (row[0], row[1])
            for row in cursor.fetchall()
            if row[1].endswith(TEMP_SUFFIX)
        ]


class Command(BaseCommand):
    help = (
        "Verify that space identifiers and every relation use UUIDs and that "
        "no conversion leftovers remain."
    )

    def handle(self, *args, **options):
        if connection.vendor != "mysql":
            raise CommandError("This check only supports MySQL/MariaDB.")

        expected = _uuid_db_type()
        problems = []
        lines = []

        space = apps.get_model("spaces", "Space")
        table = space._meta.db_table
        column = space._meta.pk.column
        info = _column(table, column)
        actual = info[0].lower() if info else "missing"
        lines.append(f"{table}.{column}: {actual}")
        if actual != expected:
            problems.append(
                f"{table}.{column} is {actual}, expected {expected}"
            )
        if not _has_primary_key(table):
            problems.append(f"{table} has no primary key")
        lines.append(f"{table}: {_row_count(table)} row(s)")

        for model, field in _space_relations():
            label = f"{model._meta.label}.{field.name}"
            table = model._meta.db_table
            info = _column(table, field.column)
            actual = info[0].lower() if info else "missing"
            if actual != expected:
                problems.append(f"{label} is {actual}, expected {expected}")
            else:
                nullable = info[1] == "YES"
                if nullable != field.null:
                    wanted = "NULL" if field.null else "NOT NULL"
                    got = "NULL" if nullable else "NOT NULL"
                    problems.append(f"{label} is {got}, expected {wanted}")
            if not _has_foreign_key(table, field.column):
                problems.append(f"{label} has no foreign key")
            orphans = 0
            if actual == expected:
                orphans = _orphan_count(table, field.column)
                if orphans:
                    problems.append(
                        f"{label}: {orphans} row(s) point at a missing space"
                    )
            lines.append(f"{table}: {_row_count(table)} row(s)")

        leftovers = _temp_columns()
        if leftovers:
            problems.append(
                "staged columns left behind: "
                + ", ".join(f"{table}.{column}" for table, column in leftovers)
            )
        if _table_exists(REFS_TABLE):
            problems.append(
                f"{REFS_TABLE} still exists; the conversion did not finish"
            )
        if _table_exists(MAPPING_TABLE):
            count = _row_count(MAPPING_TABLE)
            lines.append(f"{MAPPING_TABLE}: {count} row(s)")
        else:
            problems.append(f"{MAPPING_TABLE} is missing")

        for line in lines:
            self.stdout.write(line)
        if problems:
            raise CommandError(
                "Space UUID verification failed:\n  - "
                + "\n  - ".join(problems)
            )
        self.stdout.write(
            self.style.SUCCESS("OK: space identifiers are UUIDs")
        )

"""Convert ``Space`` primary keys from integers to UUIDs.

Django derives a foreign key's database type from the field it points at, so
changing ``Space.id`` does not generate ``AlterField`` operations for the
columns in other apps that reference it. MySQL/MariaDB also refuse to change a
referenced column while foreign keys still point at it. This migration
rewrites the primary key and every referencing column in place while keeping
the existing rows and their relations intact.

MySQL/MariaDB DDL is not transactional, so a failed run leaves the schema
partially converted. Every step therefore inspects the live schema first and
can be resumed by running ``migrate`` again:

* ``spaces_space_id_map`` pins the integer to UUID mapping. It is written
  before any data is touched, so a retry reuses the same identifiers instead
  of inventing new ones, and it stays behind for reconciliation afterwards.
* ``spaces_space_uuid_refs`` keeps the foreign keys and indexes that have to
  be detached from the converted columns. It is dropped once the conversion
  is complete, and lets a retry restore every constraint even when the first
  attempt died halfway through.

Run ``python manage.py verify_space_uuid`` after the migration to confirm the
columns, constraints and relations are consistent.
"""

import json
import uuid

from django.db import migrations, models

MAPPING_TABLE = "spaces_space_id_map"
REFS_TABLE = "spaces_space_uuid_refs"
TEMP_SUFFIX = "__uuid_tmp"


def _uuid_db_type(connection):
    if connection.features.has_native_uuid_field:
        return "uuid"
    return "char(32)"


def _uuid_param(connection, value):
    if connection.features.has_native_uuid_field:
        return str(value)
    return value.hex


def _space_relations(apps):
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


def _constraints(connection, table):
    with connection.cursor() as cursor:
        return connection.introspection.get_constraints(cursor, table)


def _column_type(connection, table, column):
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT column_type FROM information_schema.columns "
            "WHERE table_schema = DATABASE() AND table_name = %s "
            "AND column_name = %s",
            [table, column],
        )
        row = cursor.fetchone()
    return row[0].lower() if row else None


def _has_primary_key(connection, table):
    return any(
        info.get("primary_key")
        for info in _constraints(connection, table).values()
    )


def _capture_references(connection, table, column):
    """Remember the foreign keys and indexes that must survive the swap.

    A composite index that starts with ``column`` can also support a foreign
    key on another column, so every foreign key on the table is detached and
    restored, not only the one on ``column``.
    """
    foreign_keys = []
    indexes = []
    for name, info in _constraints(connection, table).items():
        columns = [str(item) for item in info.get("columns") or []]
        if info.get("foreign_key"):
            ref_table, ref_column = info["foreign_key"]
            foreign_keys.append([name, columns, ref_table, ref_column])
            continue
        if column in columns and not info.get("primary_key"):
            indexes.append([name, bool(info.get("unique")), columns])
    return {"foreign_keys": foreign_keys, "indexes": indexes}


def _create_mapping_table(schema_editor):
    connection = schema_editor.connection
    quote = connection.ops.quote_name
    schema_editor.execute(
        f"CREATE TABLE IF NOT EXISTS {quote(MAPPING_TABLE)} ("
        f"{quote('old_id')} BIGINT NOT NULL PRIMARY KEY, "
        f"{quote('new_id')} {_uuid_db_type(connection)} NOT NULL, "
        f"{quote('migrated_at')} DATETIME(6) NOT NULL "
        f"DEFAULT CURRENT_TIMESTAMP(6), "
        f"UNIQUE KEY {quote(MAPPING_TABLE + '_new_id')} ({quote('new_id')})"
        f") ENGINE=InnoDB"
    )


def _create_snapshot_table(schema_editor):
    connection = schema_editor.connection
    quote = connection.ops.quote_name
    schema_editor.execute(
        f"CREATE TABLE IF NOT EXISTS {quote(REFS_TABLE)} ("
        f"{quote('table_name')} VARCHAR(64) NOT NULL PRIMARY KEY, "
        f"{quote('payload')} LONGTEXT NOT NULL"
        f") ENGINE=InnoDB"
    )


def _drop_snapshot_table(schema_editor):
    connection = schema_editor.connection
    quote = connection.ops.quote_name
    schema_editor.execute(f"DROP TABLE IF EXISTS {quote(REFS_TABLE)}")


def _store_snapshot(schema_editor, table, payload):
    connection = schema_editor.connection
    quote = connection.ops.quote_name
    with connection.cursor() as cursor:
        cursor.execute(
            f"INSERT IGNORE INTO {quote(REFS_TABLE)} "
            f"({quote('table_name')}, {quote('payload')}) VALUES (%s, %s)",
            [table, json.dumps(payload)],
        )


def _load_snapshot(schema_editor, table):
    connection = schema_editor.connection
    quote = connection.ops.quote_name
    with connection.cursor() as cursor:
        cursor.execute(
            f"SELECT {quote('payload')} FROM {quote(REFS_TABLE)} "
            f"WHERE {quote('table_name')} = %s",
            [table],
        )
        row = cursor.fetchone()
    return json.loads(row[0]) if row else None


def _delete_snapshot(schema_editor, table):
    connection = schema_editor.connection
    quote = connection.ops.quote_name
    with connection.cursor() as cursor:
        cursor.execute(
            f"DELETE FROM {quote(REFS_TABLE)} "
            f"WHERE {quote('table_name')} = %s",
            [table],
        )


def _ensure_mapping(schema_editor, space_table):
    """Give every integer space identifier a stable UUID."""
    connection = schema_editor.connection
    quote = connection.ops.quote_name
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT {quote('old_id')} FROM {quote(MAPPING_TABLE)}")
        known = {row[0] for row in cursor.fetchall()}
        cursor.execute(f"SELECT {quote('id')} FROM {quote(space_table)}")
        missing = [row[0] for row in cursor.fetchall() if row[0] not in known]
        for old_id in missing:
            cursor.execute(
                f"INSERT IGNORE INTO {quote(MAPPING_TABLE)} "
                f"({quote('old_id')}, {quote('new_id')}) VALUES (%s, %s)",
                [old_id, _uuid_param(connection, uuid.uuid4())],
            )


def _backfill(schema_editor, table, column, temp):
    """Copy the staged UUID for every row that still has an integer value."""
    connection = schema_editor.connection
    quote = connection.ops.quote_name
    schema_editor.execute(
        f"UPDATE {quote(table)} t JOIN {quote(MAPPING_TABLE)} m "
        f"ON t.{quote(column)} = m.{quote('old_id')} "
        f"SET t.{quote(temp)} = m.{quote('new_id')} "
        f"WHERE t.{quote(temp)} IS NULL"
    )


def _assert_backfilled(schema_editor, table, column, temp):
    connection = schema_editor.connection
    quote = connection.ops.quote_name
    with connection.cursor() as cursor:
        cursor.execute(
            f"SELECT COUNT(*) FROM {quote(table)} "
            f"WHERE {quote(column)} IS NOT NULL "
            f"AND {quote(temp)} IS NULL"
        )
        missing = cursor.fetchone()[0]
    if missing:
        raise RuntimeError(
            f"{table}.{column}: {missing} row(s) were added while the "
            "migration was running and are not mapped yet. Stop write "
            "traffic and run migrate again."
        )


def _assert_referenceable(schema_editor, table, temp):
    """Every staged UUID must still point at an existing space."""
    connection = schema_editor.connection
    quote = connection.ops.quote_name
    with connection.cursor() as cursor:
        cursor.execute(
            f"SELECT COUNT(*) FROM {quote(table)} x LEFT JOIN "
            f"{quote('spaces_space')} s ON s.{quote('id')} = "
            f"x.{quote(temp)} WHERE x.{quote(temp)} IS NOT NULL "
            f"AND s.{quote('id')} IS NULL"
        )
        orphans = cursor.fetchone()[0]
    if orphans:
        raise RuntimeError(
            f"{table}.{temp}: {orphans} row(s) point at a space that no "
            "longer exists; the foreign key cannot be restored."
        )


def _drop_references(schema_editor, table, column):
    """Detach the indexes on ``column`` and every foreign key on the table."""
    connection = schema_editor.connection
    quote = connection.ops.quote_name
    captured = _capture_references(connection, table, column)
    for name, _, _, _ in captured["foreign_keys"]:
        schema_editor.execute(
            f"ALTER TABLE {quote(table)} DROP FOREIGN KEY {quote(name)}"
        )
    for name, _, _ in captured["indexes"]:
        schema_editor.execute(
            f"ALTER TABLE {quote(table)} DROP INDEX {quote(name)}"
        )


def _create_indexes(schema_editor, table, indexes):
    connection = schema_editor.connection
    quote = connection.ops.quote_name
    existing = set(_constraints(connection, table))
    for name, unique, columns in indexes:
        if name in existing:
            continue
        kind = "UNIQUE INDEX" if unique else "INDEX"
        quoted_columns = ", ".join(quote(item) for item in columns)
        schema_editor.execute(
            f"CREATE {kind} {quote(name)} ON {quote(table)} "
            f"({quoted_columns})"
        )


def _create_foreign_keys(schema_editor, table, foreign_keys):
    connection = schema_editor.connection
    quote = connection.ops.quote_name
    constraints = _constraints(connection, table)
    pending = []
    for name, columns, ref_table, ref_column in foreign_keys:
        info = constraints.get(name)
        if info is not None and info.get("foreign_key"):
            continue
        if info is not None:
            # Dropping a foreign key leaves its supporting index behind on
            # MySQL/MariaDB, and the leftover index is named after the
            # constraint. Remove it first or the constraint cannot come back.
            if info.get("unique"):
                raise RuntimeError(
                    f"{table}.{name}: a unique index still uses the foreign "
                    "key's name; inspect the table before adding the "
                    "constraint back."
                )
            schema_editor.execute(
                f"ALTER TABLE {quote(table)} DROP INDEX {quote(name)}"
            )
        pending.append((name, columns, ref_table, ref_column))
    for name, columns, ref_table, ref_column in pending:
        quoted_columns = ", ".join(quote(item) for item in columns)
        schema_editor.execute(
            f"ALTER TABLE {quote(table)} ADD CONSTRAINT {quote(name)} "
            f"FOREIGN KEY ({quoted_columns}) REFERENCES "
            f"{quote(ref_table)} ({quote(ref_column)})"
        )


def _restore_references(schema_editor, table, payload):
    _create_indexes(schema_editor, table, payload["indexes"])
    _create_foreign_keys(schema_editor, table, payload["foreign_keys"])


def forwards(apps, schema_editor):
    connection = schema_editor.connection
    if connection.vendor != "mysql":
        raise NotImplementedError(
            "Converting Space primary keys to UUID requires MySQL/MariaDB."
        )

    quote = connection.ops.quote_name
    Space = apps.get_model("spaces", "Space")
    space_table = Space._meta.db_table
    space_pk = Space._meta.pk.column
    uuid_type = _uuid_db_type(connection)

    existing_tables = set(connection.introspection.table_names())
    if space_table not in existing_tables:
        return

    _create_mapping_table(schema_editor)
    _create_snapshot_table(schema_editor)

    relations = []
    for model, field in _space_relations(apps):
        if model._meta.db_table not in existing_tables:
            continue
        relations.append(
            {
                "table": model._meta.db_table,
                "column": field.column,
                "null": field.null,
                "temp": f"{field.column}{TEMP_SUFFIX}",
            }
        )

    parent_is_uuid = (
        _column_type(connection, space_table, space_pk) == uuid_type
    )
    if not parent_is_uuid:
        # Pin the mapping before touching any data: a retry has to reuse the
        # same UUIDs or the parent and child rows would stop matching.
        _ensure_mapping(schema_editor, space_table)

    # Detach every child column and stage its new UUID value. The old integer
    # value is kept until the parent primary key has been replaced.
    for relation in relations:
        table = relation["table"]
        column = relation["column"]
        temp = relation["temp"]
        column_type = _column_type(connection, table, column)
        if column_type is None or column_type == uuid_type:
            # Missing here means the swap died between the two statements
            # below; it is finished by the third phase.
            continue
        if _column_type(connection, table, temp) is None:
            payload = _capture_references(connection, table, column)
            _store_snapshot(schema_editor, table, payload)
            _drop_references(schema_editor, table, column)
            schema_editor.execute(
                f"ALTER TABLE {quote(table)} ADD COLUMN "
                f"{quote(temp)} {uuid_type} NULL"
            )
        _backfill(schema_editor, table, column, temp)

    # Replace the integer primary key. AUTO_INCREMENT has to be removed before
    # the primary key can be dropped, and the column is swapped afterwards so
    # no integer value ever needs to be cast to a UUID.
    parent_temp = f"{space_pk}{TEMP_SUFFIX}"
    if not parent_is_uuid:
        if _column_type(connection, space_table, space_pk) is None:
            # Died between dropping the column and renaming the staged one;
            # the staged column already holds every value.
            pass
        else:
            # Anything created while the migration was running also needs a
            # UUID before the old column is dropped.
            _ensure_mapping(schema_editor, space_table)
            for relation in relations:
                table = relation["table"]
                column = relation["column"]
                temp = relation["temp"]
                if _column_type(connection, table, temp) is None:
                    continue
                if _column_type(connection, table, column) is None:
                    continue
                _backfill(schema_editor, table, column, temp)
            schema_editor.execute(
                f"ALTER TABLE {quote(space_table)} "
                f"MODIFY {quote(space_pk)} BIGINT NOT NULL"
            )
            if _column_type(connection, space_table, parent_temp) is None:
                schema_editor.execute(
                    f"ALTER TABLE {quote(space_table)} ADD COLUMN "
                    f"{quote(parent_temp)} {uuid_type} NULL"
                )
            _backfill(schema_editor, space_table, space_pk, parent_temp)
            _assert_backfilled(
                schema_editor, space_table, space_pk, parent_temp
            )
            if _has_primary_key(connection, space_table):
                schema_editor.execute(
                    f"ALTER TABLE {quote(space_table)} DROP PRIMARY KEY"
                )
            if _column_type(connection, space_table, space_pk) is not None:
                schema_editor.execute(
                    f"ALTER TABLE {quote(space_table)} "
                    f"DROP COLUMN {quote(space_pk)}"
                )
        schema_editor.execute(
            f"ALTER TABLE {quote(space_table)} CHANGE COLUMN "
            f"{quote(parent_temp)} {quote(space_pk)} {uuid_type} NOT NULL"
        )
        schema_editor.execute(
            f"ALTER TABLE {quote(space_table)} ADD PRIMARY KEY "
            f"({quote(space_pk)})"
        )
    elif not _has_primary_key(connection, space_table):
        schema_editor.execute(
            f"ALTER TABLE {quote(space_table)} ADD PRIMARY KEY "
            f"({quote(space_pk)})"
        )

    # Swap each child column and put its indexes and foreign key back.
    for relation in relations:
        table = relation["table"]
        column = relation["column"]
        temp = relation["temp"]
        column_type = _column_type(connection, table, column)
        if column_type == uuid_type:
            payload = _load_snapshot(schema_editor, table)
            if payload is not None:
                _restore_references(schema_editor, table, payload)
                _delete_snapshot(schema_editor, table)
            continue
        if _column_type(connection, table, temp) is None:
            raise RuntimeError(
                f"{table}.{column} still holds integer identifiers but the "
                f"staged column {temp} is missing. Inspect the table before "
                "running migrate again."
            )
        if column_type is not None:
            _assert_backfilled(schema_editor, table, column, temp)
            _assert_referenceable(schema_editor, table, temp)
            schema_editor.execute(
                f"ALTER TABLE {quote(table)} DROP COLUMN {quote(column)}"
            )
        payload = _load_snapshot(schema_editor, table)
        if payload is None:
            raise RuntimeError(
                f"{table}.{column} is not converted and no constraint "
                "snapshot was kept for it. Restore the backup taken before "
                "the migration."
            )
        nullability = "NULL" if relation["null"] else "NOT NULL"
        schema_editor.execute(
            f"ALTER TABLE {quote(table)} CHANGE COLUMN {quote(temp)} "
            f"{quote(column)} {uuid_type} {nullability}"
        )
        _restore_references(schema_editor, table, payload)
        _delete_snapshot(schema_editor, table)

    unfinished = [
        relation["table"]
        for relation in relations
        if _column_type(
            connection, relation["table"], relation["column"]
        ) != uuid_type
    ]
    if unfinished:
        raise RuntimeError(
            "Space UUID conversion left these tables unconverted: "
            + ", ".join(unfinished)
        )
    _drop_snapshot_table(schema_editor)


class Migration(migrations.Migration):
    # MySQL/MariaDB DDL commits implicitly, so wrapping the conversion in a
    # transaction would not make it reversible. Each step is resumable
    # instead.
    atomic = False

    dependencies = [
        ("spaces", "0001_initial"),
        ("chat_analysis", "0001_initial"),
        ("chat_domain", "0001_initial"),
        ("chat_ingestion", "0001_initial"),
        ("chat_sources", "0001_initial"),
        ("threadline", "0043_add_space_to_email_resources"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(forwards),
            ],
            state_operations=[
                migrations.AlterField(
                    model_name="space",
                    name="id",
                    field=models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
            ],
        ),
    ]

"""Convert ``Space`` primary keys from integers to UUIDs.

Django derives a foreign key's database type from the field it points at, so
changing ``Space.id`` does not generate ``AlterField`` operations for the
columns in other apps that reference it. MySQL/MariaDB also refuse to change a
referenced column while foreign keys still point at it. This migration
rewrites the primary key and every referencing column in place while keeping
the existing rows and their relations intact.
"""

import uuid

from django.db import migrations, models


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


def _drop_references(schema_editor, table, column):
    """Drop indexes that use ``column`` and every foreign key on the table.

    A composite index that starts with ``column`` can also support a foreign
    key on another column, so all foreign keys are detached first and restored
    after the column swap.
    """
    connection = schema_editor.connection
    quote = connection.ops.quote_name
    with connection.cursor() as cursor:
        constraints = connection.introspection.get_constraints(cursor, table)

    foreign_keys = []
    indexes = []
    for name, info in constraints.items():
        columns = info.get("columns") or []
        if info.get("foreign_key"):
            ref_table, ref_column = info["foreign_key"]
            foreign_keys.append((name, columns, ref_table, ref_column))
            continue
        if column in columns and not info.get("primary_key"):
            indexes.append((name, info.get("unique", False), columns))

    for name, _, _, _ in foreign_keys:
        schema_editor.execute(
            f"ALTER TABLE {quote(table)} DROP FOREIGN KEY {quote(name)}"
        )
    for name, _, _ in indexes:
        schema_editor.execute(
            f"ALTER TABLE {quote(table)} DROP INDEX {quote(name)}"
        )
    return foreign_keys, indexes


def _create_indexes(schema_editor, table, indexes):
    connection = schema_editor.connection
    quote = connection.ops.quote_name
    for name, unique, columns in indexes:
        kind = "UNIQUE INDEX" if unique else "INDEX"
        quoted_columns = ", ".join(quote(item) for item in columns)
        schema_editor.execute(
            f"CREATE {kind} {quote(name)} ON {quote(table)} "
            f"({quoted_columns})"
        )


def _create_foreign_keys(schema_editor, table, foreign_keys):
    connection = schema_editor.connection
    quote = connection.ops.quote_name
    for name, columns, ref_table, ref_column in foreign_keys:
        quoted_columns = ", ".join(quote(item) for item in columns)
        schema_editor.execute(
            f"ALTER TABLE {quote(table)} ADD CONSTRAINT {quote(name)} "
            f"FOREIGN KEY ({quoted_columns}) REFERENCES "
            f"{quote(ref_table)} ({quote(ref_column)})"
        )


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

    old_ids = list(
        Space.objects.using(connection.alias).values_list("pk", flat=True)
    )
    mapping = {old_id: uuid.uuid4() for old_id in old_ids}

    relations = []
    for model, field in _space_relations(apps):
        if model._meta.db_table not in existing_tables:
            continue
        relations.append(
            {
                "table": model._meta.db_table,
                "column": field.column,
                "null": field.null,
                "temp": f"{field.column}__uuid_tmp",
            }
        )

    # Detach every child column and stage its new UUID value. The old integer
    # value is kept until the parent primary key has been replaced.
    for relation in relations:
        table = relation["table"]
        column = relation["column"]
        temp = relation["temp"]
        foreign_keys, indexes = _drop_references(schema_editor, table, column)
        relation["foreign_keys"] = foreign_keys
        relation["indexes"] = indexes

        schema_editor.execute(
            f"ALTER TABLE {quote(table)} ADD COLUMN {quote(temp)} "
            f"{uuid_type} NULL"
        )
        for old_id, new_id in mapping.items():
            schema_editor.execute(
                f"UPDATE {quote(table)} SET {quote(temp)} = %s "
                f"WHERE {quote(column)} = %s",
                [_uuid_param(connection, new_id), old_id],
            )

    # Replace the integer primary key. AUTO_INCREMENT has to be removed before
    # the primary key can be dropped, and the column is swapped afterwards so
    # no integer value ever needs to be cast to a UUID.
    parent_temp = f"{space_pk}__uuid_tmp"
    schema_editor.execute(
        f"ALTER TABLE {quote(space_table)} "
        f"MODIFY {quote(space_pk)} BIGINT NOT NULL"
    )
    schema_editor.execute(
        f"ALTER TABLE {quote(space_table)} ADD COLUMN "
        f"{quote(parent_temp)} {uuid_type} NULL"
    )
    for old_id, new_id in mapping.items():
        schema_editor.execute(
            f"UPDATE {quote(space_table)} SET {quote(parent_temp)} = %s "
            f"WHERE {quote(space_pk)} = %s",
            [_uuid_param(connection, new_id), old_id],
        )
    schema_editor.execute(f"ALTER TABLE {quote(space_table)} DROP PRIMARY KEY")
    schema_editor.execute(
        f"ALTER TABLE {quote(space_table)} DROP COLUMN {quote(space_pk)}"
    )
    schema_editor.execute(
        f"ALTER TABLE {quote(space_table)} CHANGE COLUMN "
        f"{quote(parent_temp)} {quote(space_pk)} {uuid_type} NOT NULL"
    )
    schema_editor.execute(
        f"ALTER TABLE {quote(space_table)} ADD PRIMARY KEY "
        f"({quote(space_pk)})"
    )

    # Swap each child column and rebuild its indexes and foreign key.
    for relation in relations:
        table = relation["table"]
        column = relation["column"]
        temp = relation["temp"]
        schema_editor.execute(
            f"ALTER TABLE {quote(table)} DROP COLUMN {quote(column)}"
        )
        nullability = "NULL" if relation["null"] else "NOT NULL"
        schema_editor.execute(
            f"ALTER TABLE {quote(table)} CHANGE COLUMN {quote(temp)} "
            f"{quote(column)} {uuid_type} {nullability}"
        )
        _create_indexes(schema_editor, table, relation["indexes"])
        _create_foreign_keys(schema_editor, table, relation["foreign_keys"])


class Migration(migrations.Migration):
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

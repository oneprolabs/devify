"""Keep pre-relevance binaries able to delete parent rows during rollback."""

from django.db import migrations


FOREIGN_KEYS = (
    ("chat_domain", "ConversationIdentity", ("conversation", "user"), "ci"),
    (
        "chat_analysis",
        "EventParticipantEvidence",
        ("message", "suggestion"),
        "epe",
    ),
)


def _set_delete_rule(apps, schema_editor, rule):
    connection = schema_editor.connection
    if connection.vendor != "mysql":
        # The blue/green deployment shares a MariaDB database.
        return

    quote = connection.ops.quote_name
    for app, model_name, fields, prefix in FOREIGN_KEYS:
        model = apps.get_model(app, model_name)
        table = model._meta.db_table
        with connection.cursor() as cursor:
            constraints = connection.introspection.get_constraints(
                cursor, table,
            )
        changes = []
        for field_name in fields:
            field = model._meta.get_field(field_name)
            target_table = field.target_field.model._meta.db_table
            target_column = field.target_field.column
            (old_name,) = (
                name for name, constraint in constraints.items()
                if constraint["columns"] == [field.column]
                and constraint["foreign_key"] == (target_table, target_column)
            )
            new_name = f"chat_{prefix}_{field_name}_{rule.lower()}"
            if old_name == new_name:
                continue
            changes.extend((
                f"DROP FOREIGN KEY {quote(old_name)}",
                f"ADD CONSTRAINT {quote(new_name)} "
                f"FOREIGN KEY ({quote(field.column)}) "
                f"REFERENCES {quote(target_table)} ({quote(target_column)}) "
                f"ON DELETE {rule}",
            ))
        if changes:
            schema_editor.execute(
                f"ALTER TABLE {quote(table)} " + ", ".join(changes)
            )


def forwards(apps, schema_editor):
    _set_delete_rule(apps, schema_editor, "CASCADE")


def backwards(apps, schema_editor):
    _set_delete_rule(apps, schema_editor, "RESTRICT")


class Migration(migrations.Migration):
    atomic = False
    dependencies = [("chat_analysis", "0011_event_participant_identity")]
    operations = [migrations.RunPython(forwards, backwards)]

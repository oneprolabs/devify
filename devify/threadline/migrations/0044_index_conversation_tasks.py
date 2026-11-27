"""Index conversation task lookups without editing AgentCore's model."""

from django.db import migrations


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("agentcore_task_tracker", "0002_rename_execution_table"),
        ("threadline", "0043_add_space_to_email_resources"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                ALTER TABLE agentcore_task_execution WAIT 5
                ADD COLUMN IF NOT EXISTS threadline_email_key
                    VARCHAR(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin
                    GENERATED ALWAYS AS (
                        CASE WHEN CHAR_LENGTH(RTRIM(JSON_UNQUOTE(
                            JSON_EXTRACT(metadata, '$.context.email_id')
                        ))) <= 20 THEN RTRIM(JSON_UNQUOTE(
                            JSON_EXTRACT(metadata, '$.context.email_id')
                        )) END
                    ) VIRTUAL,
                ALGORITHM=INSTANT, LOCK=NONE
            """,
            reverse_sql="""
                ALTER TABLE agentcore_task_execution WAIT 5
                DROP COLUMN IF EXISTS threadline_email_key,
                ALGORITHM=INSTANT, LOCK=NONE
            """,
        ),
        migrations.RunSQL(
            sql="""
                ALTER TABLE agentcore_task_execution WAIT 5
                ADD INDEX IF NOT EXISTS threadline_email_created_idx
                    (threadline_email_key, created_at, id),
                ALGORITHM=INPLACE, LOCK=NONE
            """,
            reverse_sql="""
                ALTER TABLE agentcore_task_execution WAIT 5
                DROP INDEX IF EXISTS threadline_email_created_idx,
                ALGORITHM=INPLACE, LOCK=NONE
            """,
        ),
    ]

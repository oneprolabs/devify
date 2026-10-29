from django.db import migrations, models
from django.db.models import OuterRef, Subquery
import django.db.models.deletion


def backfill_email_spaces(apps, schema_editor):
    Space = apps.get_model("spaces", "Space")
    database = schema_editor.connection.alias
    personal_space = Space.objects.using(database).filter(
        personal_owner_id=OuterRef("user_id")
    ).values("pk")[:1]
    for model_name in ("EmailMailbox", "EmailMessage"):
        model = apps.get_model("threadline", model_name)
        model.objects.using(database).filter(space__isnull=True).update(
            space_id=Subquery(personal_space)
        )
    email = apps.get_model("threadline", "EmailMessage")
    attachment = apps.get_model("threadline", "EmailAttachment")
    email_space = email.objects.using(database).filter(
        pk=OuterRef("email_message_id")
    ).values("space_id")[:1]
    attachment.objects.using(database).filter(space__isnull=True).update(
        space_id=Subquery(email_space)
    )


class Migration(migrations.Migration):
    dependencies = [
        ("spaces", "0003_spacetakeover"),
        ("threadline", "0042_move_filters_onto_mailboxes"),
    ]

    operations = [
        migrations.AddField(
            model_name="emailmessage",
            name="space",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="email_messages",
                to="spaces.space",
            ),
        ),
        migrations.AddField(
            model_name="emailattachment",
            name="space",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="email_attachments",
                to="spaces.space",
            ),
        ),
        migrations.AddField(
            model_name="emailmailbox",
            name="space",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="email_mailboxes",
                to="spaces.space",
            ),
        ),
        migrations.RunPython(backfill_email_spaces, migrations.RunPython.noop),
    ]

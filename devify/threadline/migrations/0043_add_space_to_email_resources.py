"""Add email spaces, shared mailbox sources and the duplicate backfill.

This is the unreleased branch's combined migration. It adds the ``space``
columns and the personal-space backfill, then the unique mailbox source,
the space shares, the message-to-mailbox link, the nullable technical owner,
and the duplicate-source merge.

Existing deployments could configure the same IMAP account more than once.
The oldest row becomes the canonical source; duplicates are disabled but kept
for audit, and their owner spaces become shares on the canonical mailbox.
"""

import hashlib

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
from django.db.models import OuterRef, Subquery


def backfill_email_spaces(apps, schema_editor):
    Space = apps.get_model("spaces", "Space")
    database = schema_editor.connection.alias
    personal_space = (
        Space.objects.using(database)
        .filter(personal_owner_id=OuterRef("user_id"))
        .values("pk")[:1]
    )
    for model_name in ("EmailMailbox", "EmailMessage"):
        model = apps.get_model("threadline", model_name)
        model.objects.using(database).filter(space__isnull=True).update(
            space_id=Subquery(personal_space)
        )
    email = apps.get_model("threadline", "EmailMessage")
    attachment = apps.get_model("threadline", "EmailAttachment")
    email_space = (
        email.objects.using(database)
        .filter(pk=OuterRef("email_message_id"))
        .values("space_id")[:1]
    )
    attachment.objects.using(database).filter(space__isnull=True).update(
        space_id=Subquery(email_space)
    )


def _source_key(imap_host, imap_port, username, folder, use_ssl):
    raw = "|".join(
        (
            str(imap_host or "").strip().lower(),
            str(int(imap_port or 993)),
            str(username or "").strip(),
            str(folder or "INBOX").strip() or "INBOX",
            "1" if use_ssl else "0",
        )
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def backfill_source_keys_and_shares(apps, schema_editor):
    Space = apps.get_model("spaces", "Space")
    EmailMailbox = apps.get_model("threadline", "EmailMailbox")
    EmailMailboxShare = apps.get_model("threadline", "EmailMailboxShare")

    personal_by_user = dict(
        Space.objects.filter(personal_owner__isnull=False).values_list(
            "personal_owner_id", "pk"
        )
    )

    groups = {}
    for mailbox in EmailMailbox.objects.order_by("id").iterator():
        if mailbox.space_id is None:
            mailbox.space_id = personal_by_user.get(mailbox.user_id)
        mailbox.source_key = _source_key(
            mailbox.imap_host,
            mailbox.imap_port,
            mailbox.username,
            mailbox.folder,
            mailbox.use_ssl,
        )
        mailbox.save(update_fields=("space_id", "source_key"))
        groups.setdefault(mailbox.source_key, []).append(mailbox)

    for source_key, mailboxes in groups.items():
        canonical = mailboxes[0]
        for duplicate in mailboxes[1:]:
            if (
                duplicate.space_id is not None
                and duplicate.space_id != canonical.space_id
            ):
                EmailMailboxShare.objects.get_or_create(
                    mailbox=canonical,
                    space_id=duplicate.space_id,
                    defaults={
                        "permission": "manage",
                        "created_by_id": duplicate.created_by_id,
                    },
                )
            newer_credentials = duplicate.last_success_at and (
                canonical.last_success_at is None
                or duplicate.last_success_at > canonical.last_success_at
            )
            if newer_credentials:
                # Keep the credential set that most recently worked; the
                # source key does not include the password.
                canonical.imap_host = duplicate.imap_host
                canonical.imap_port = duplicate.imap_port
                canonical.use_ssl = duplicate.use_ssl
                canonical.username = duplicate.username
                canonical.password = duplicate.password
                canonical.folder = duplicate.folder
                canonical.last_fetched_at = duplicate.last_fetched_at
                canonical.last_success_at = duplicate.last_success_at
                canonical.save(
                    update_fields=(
                        "imap_host",
                        "imap_port",
                        "use_ssl",
                        "username",
                        "password",
                        "folder",
                        "last_fetched_at",
                        "last_success_at",
                    )
                )
            elif duplicate.last_fetched_at and (
                canonical.last_fetched_at is None
                or duplicate.last_fetched_at > canonical.last_fetched_at
            ):
                canonical.last_fetched_at = duplicate.last_fetched_at
                canonical.last_success_at = duplicate.last_success_at
                canonical.save(
                    update_fields=("last_fetched_at", "last_success_at")
                )
            # Keep the row for audit but release the unique source key.
            duplicate.source_key = f"merged:{duplicate.pk}"
            duplicate.enabled = False
            duplicate.save(update_fields=("source_key", "enabled"))

        if canonical.space_id is not None:
            EmailMailboxShare.objects.get_or_create(
                mailbox=canonical,
                space_id=canonical.space_id,
                defaults={
                    "permission": "manage",
                    "created_by_id": canonical.created_by_id,
                },
            )


class Migration(migrations.Migration):

    dependencies = [
        ("spaces", "0001_initial"),
        ("threadline", "0042_move_filters_onto_mailboxes"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
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
        migrations.RunPython(
            backfill_email_spaces,
            migrations.RunPython.noop,
        ),
        migrations.CreateModel(
            name="EmailMailboxShare",
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
                    "permission",
                    models.CharField(
                        choices=[("read", "Read"), ("manage", "Manage")],
                        default="read",
                        max_length=20,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "verbose_name": "Email Mailbox Share",
                "verbose_name_plural": "Email Mailbox Shares",
                "ordering": ["id"],
            },
        ),
        migrations.RemoveConstraint(
            model_name="emailmailbox",
            name="threadline_mailbox_user_host_username_uniq",
        ),
        migrations.AlterUniqueTogether(
            name="emailmessage",
            unique_together=set(),
        ),
        migrations.AddField(
            model_name="emailmailbox",
            name="created_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="created_email_mailboxes",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="emailmailbox",
            name="source_key",
            field=models.CharField(
                blank=True,
                db_index=True,
                editable=False,
                max_length=64,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="emailmessage",
            name="mailbox",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="messages",
                to="threadline.emailmailbox",
            ),
        ),
        migrations.AlterUniqueTogether(
            name="emailmessage",
            unique_together={("mailbox", "message_id")},
        ),
        migrations.AddIndex(
            model_name="emailmessage",
            index=models.Index(
                fields=["mailbox", "received_at"],
                name="threadline__mailbox_3053bc_idx",
            ),
        ),
        migrations.AddField(
            model_name="emailmailboxshare",
            name="created_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="created_email_mailbox_shares",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="emailmailboxshare",
            name="mailbox",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="shares",
                to="threadline.emailmailbox",
            ),
        ),
        migrations.AddField(
            model_name="emailmailboxshare",
            name="space",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="email_mailbox_shares",
                to="spaces.space",
            ),
        ),
        migrations.AddIndex(
            model_name="emailmailboxshare",
            index=models.Index(
                fields=["space", "mailbox"],
                name="threadline__space_i_7f005a_idx",
            ),
        ),
        migrations.AlterUniqueTogether(
            name="emailmailboxshare",
            unique_together={("mailbox", "space")},
        ),
        migrations.AlterField(
            model_name="emailmailbox",
            name="user",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="mailboxes",
                to=settings.AUTH_USER_MODEL,
                verbose_name="User",
            ),
        ),
        migrations.RunPython(
            backfill_source_keys_and_shares,
            migrations.RunPython.noop,
        ),
        migrations.AlterField(
            model_name="emailmailbox",
            name="source_key",
            field=models.CharField(
                db_index=True,
                editable=False,
                max_length=64,
                unique=True,
            ),
        ),
    ]

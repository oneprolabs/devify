"""Backfill the unique mailbox source key and its space shares.

Existing deployments could configure the same IMAP account more than once.
This migration gives every mailbox a source key, keeps the oldest row as the
canonical source, disables the duplicates and turns their owner space into a
share on the canonical mailbox. Duplicate rows are kept (disabled) so the
change can be inspected or rolled back without losing credentials/state.
"""

import hashlib

from django.db import migrations, models


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
        ("threadline", "0044_mailbox_source_and_shares"),
    ]

    operations = [
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

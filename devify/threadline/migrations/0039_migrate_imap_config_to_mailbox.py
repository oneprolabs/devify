"""
Move each user's single IMAP configuration into its own mailbox row.

The old layout stored one `imap_config` inside the `email_config` settings
blob and used a `mode` flag to decide whether it applied. Mailboxes are now
separate records that run alongside the virtual address, so every existing
custom_imap configuration becomes one mailbox.
"""

from django.db import migrations


def forwards(apps, schema_editor):
    Settings = apps.get_model("threadline", "Settings")
    EmailMailbox = apps.get_model("threadline", "EmailMailbox")

    # The historical model keeps the real field class, so passwords that
    # were sitting in plain text inside the settings blob are encrypted on
    # the way into their new home.
    for setting in Settings.objects.filter(key="email_config", is_active=True):
        config = setting.value or {}
        if config.get("mode") != "custom_imap":
            continue

        imap = config.get("imap_config") or {}
        host = (imap.get("imap_host") or "").strip()
        username = (imap.get("username") or "").strip()
        if not host or not username:
            continue

        if EmailMailbox.objects.filter(
            user_id=setting.user_id, imap_host=host, username=username
        ).exists():
            continue

        use_ssl = imap.get("use_ssl", True)
        port = (
            imap.get("imap_ssl_port")
            or imap.get("imap_port")
            or (993 if use_ssl else 143)
        )

        EmailMailbox.objects.create(
            user_id=setting.user_id,
            name=username,
            imap_host=host,
            imap_port=int(port),
            use_ssl=bool(use_ssl),
            username=username,
            password=imap.get("password") or "",
            folder=imap.get("folder") or "INBOX",
            delete_after_fetch=bool(imap.get("delete_after_fetch", False)),
            enabled=True,
        )


def backwards(apps, schema_editor):
    # The settings blob is left untouched going forward, so the original
    # configuration is still there to fall back on.
    EmailMailbox = apps.get_model("threadline", "EmailMailbox")
    EmailMailbox.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("threadline", "0038_emailmailbox"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]

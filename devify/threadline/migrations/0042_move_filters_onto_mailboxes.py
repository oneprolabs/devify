"""Give every mailbox the filters it was inheriting from the account."""

from django.db import migrations


def copy_account_filters_onto_mailboxes(apps, schema_editor):
    """
    Carry the account's filters onto each mailbox that had none.

    Filters used to live on the account and apply to every mailbox. Now
    each mailbox owns its own, so an account value that is not copied
    across would simply stop applying - most visibly the age limit, which
    is what keeps a first fetch from pulling in years of mail.
    """
    Settings = apps.get_model("threadline", "Settings")
    EmailMailbox = apps.get_model("threadline", "EmailMailbox")

    for setting in Settings.objects.filter(key="email_config", is_active=True):
        config = (setting.value or {}).get("filter_config") or {}
        filters = config.get("filters") or []
        excludes = config.get("exclude_patterns") or []
        max_age = config.get("max_age_days")

        if not (filters or excludes or max_age is not None):
            continue

        for mailbox in EmailMailbox.objects.filter(user_id=setting.user_id):
            changed = []
            if filters and not mailbox.filters:
                mailbox.filters = list(filters)
                changed.append("filters")
            if excludes and not mailbox.exclude_patterns:
                mailbox.exclude_patterns = list(excludes)
                changed.append("exclude_patterns")
            if max_age is not None and mailbox.max_age_days is None:
                mailbox.max_age_days = max_age
                changed.append("max_age_days")
            if changed:
                mailbox.save(update_fields=changed)


def noop(apps, schema_editor):
    """The mailbox values stand on their own; nothing to undo."""


class Migration(migrations.Migration):

    dependencies = [
        ("threadline", "0041_emailmailbox_exclude_patterns_emailmailbox_filters_and_more"),
    ]

    operations = [
        migrations.RunPython(copy_account_filters_onto_mailboxes, noop),
    ]

"""Drop the uploading account from the conversation identity.

Conversations were keyed by ``platform + source namespace + source
conversation``, so two people exporting the same group produced two rows.
The key is now ``platform + source conversation``. This migration rewrites
the stored keys and folds the rows that collide into the oldest conversation.

Messages are moved without being reinterpreted: a message key that already
exists in the surviving conversation is renamed to a ``legacy:`` key and the
original name is registered as a per-namespace alias, so the account that
used it can still resolve the message on its next upload. Fingerprint
merging of the remaining duplicates is a separate, reviewable command.

The reverse is intentionally a no-op: restoring the account dimension would
require knowing which upload created each message, which is not recorded on
the conversation row anymore.
"""

from django.db import migrations
from django.db.models import Count, Max


def _new_key(identity_key):
    """``platform:namespace:component`` -> ``platform:component``."""
    parts = identity_key.split(":")
    if len(parts) < 3:
        return ""
    return f"{parts[0]}:{parts[-1]}"


def forwards(apps, schema_editor):
    Conversation = apps.get_model("chat_domain", "Conversation")
    Message = apps.get_model("chat_domain", "Message")
    MessageAlias = apps.get_model("chat_domain", "MessageAlias")

    for conversation in Conversation.objects.all().iterator():
        new_key = _new_key(conversation.identity_key)
        if new_key and conversation.identity_key != new_key:
            conversation.identity_key = new_key
            conversation.save(update_fields=("identity_key", "updated_at"))

    groups = list(
        Conversation.objects.values("space_id", "identity_key")
        .annotate(total=Count("id"))
        .filter(total__gt=1)
    )
    for group in groups:
        siblings = list(
            Conversation.objects.filter(
                space_id=group["space_id"], identity_key=group["identity_key"]
            ).order_by("id")
        )
        target, extras = siblings[0], siblings[1:]
        existing = set(
            Message.objects.filter(conversation=target).values_list(
                "message_key", flat=True
            )
        )
        next_seq = (
            Message.objects.filter(conversation=target).aggregate(
                last=Max("ingest_seq")
            )["last"]
            or 0
        )
        namespaces = list(
            (target.metadata or {}).get("source_namespaces") or []
        )
        for extra in extras:
            for message in Message.objects.filter(
                conversation=extra
            ).order_by("ingest_seq", "id"):
                original_key = message.message_key
                if original_key in existing:
                    MessageAlias.objects.get_or_create(
                        conversation=target,
                        source_namespace=extra.source_namespace,
                        alias_key=original_key[:500],
                        defaults={"message": message},
                    )
                    message.message_key = (
                        f"legacy:{extra.pk}:{original_key}"[:500]
                    )
                next_seq += 1
                message.conversation_id = target.pk
                message.ingest_seq = next_seq
                message.save(
                    update_fields=(
                        "conversation",
                        "ingest_seq",
                        "message_key",
                    )
                )
                existing.add(message.message_key)
            if extra.source_namespace and (
                extra.source_namespace not in namespaces
            ):
                namespaces.append(extra.source_namespace)
            extra.delete()

        summary = Message.objects.filter(conversation=target).aggregate(
            last=Max("occurred_at")
        )
        target.message_count = Message.objects.filter(
            conversation=target
        ).count()
        target.last_message_at = summary["last"]
        metadata = dict(target.metadata or {})
        if namespaces:
            metadata["source_namespaces"] = namespaces
        target.metadata = metadata
        target.save(
            update_fields=(
                "message_count",
                "last_message_at",
                "metadata",
                "updated_at",
            )
        )


class Migration(migrations.Migration):

    dependencies = [
        (
            "chat_domain",
            "0003_message_content_fingerprint_message_orphaned_at_and_more",
        ),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]

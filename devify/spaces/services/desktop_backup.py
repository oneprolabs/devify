"""Persist desktop settings and resolve bounded backup lookups."""

import hashlib
import json

from django.db import transaction

from accounts.models import DesktopDevice
from chat_domain.models import Conversation, Message, MessageAlias
from spaces.models import DesktopBackupConfig, DesktopConfigReceipt


class DeviceAuthorizationRequired(Exception):
    """The desktop device is not active for the requesting user."""


class IdempotencyKeyReused(Exception):
    """A mutation key was previously saved with a different payload."""


class AmbiguousConversation(Exception):
    """More than one conversation matches the supplied source scope."""


@transaction.atomic
def save_backup_config(user, space, values):
    """Save the validated configuration and its idempotency receipt."""
    device = (
        DesktopDevice.objects.select_for_update()
        .filter(
            user=user,
            device_id=values["device_id"],
            status=DesktopDevice.Status.ACTIVE,
        )
        .first()
    )
    if device is None:
        raise DeviceAuthorizationRequired
    digest = hashlib.sha256(
        json.dumps(values, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    scope = dict(user=user, space=space, device_id=device.device_id)
    receipt = DesktopConfigReceipt.objects.filter(
        **scope, mutation_id=values["mutation_id"]
    ).first()
    if receipt:
        if receipt.digest != digest:
            raise IdempotencyKeyReused
        return receipt.result
    target = (
        values["target"]["platform"]
        + ":"
        + values["target"]["source_account_id"]
    )
    config, _ = DesktopBackupConfig.objects.get_or_create(
        **scope, target=target
    )
    payload = values["payload"]
    if payload["setup_state"] == "completed":
        config.completed = payload
        config.draft = {}
    else:
        config.draft = payload
    config.save(update_fields=("completed", "draft", "updated_at"))
    result = {
        "mutation_id": values["mutation_id"],
        "local_revision": values["local_revision"],
        "target": values["target"],
        "saved": True,
    }
    DesktopConfigReceipt.objects.create(
        **scope,
        mutation_id=values["mutation_id"],
        digest=digest,
        result=result,
    )
    return result


def find_message_keys(space, account, name, keys):
    """Resolve only the requested keys within the existing source scope."""
    conversations = list(
        Conversation.objects.filter(
            space=space, platform="wechat", source_conversation_id=name
        )[:2]
    )
    if len(conversations) > 1:
        raise AmbiguousConversation
    found = []
    if conversations:
        c = conversations[0]
        # Canonical keys may belong to another source account.
        # Namespace aliases identify local src IDs after consolidation.
        aliases = MessageAlias.objects.filter(
            conversation=c,
            source_namespace=account,
            alias_key__in=keys,
        ).select_related("message")
        found.extend(
            {
                "message_key": a.alias_key,
                "occurred_at": a.message.occurred_at,
            }
            for a in aliases
        )
        alias_keys = {item["message_key"] for item in found}
        if c.source_namespace == account:
            rows = Message.objects.filter(
                conversation=c, message_key__in=set(keys) - alias_keys
            )
            found.extend(
                {
                    "message_key": m.message_key,
                    "occurred_at": m.occurred_at,
                }
                for m in rows
            )
    return found


def find_conversation(space, platform, account, name):
    """Find a conversation using the existing backup lookup rules."""
    rows = list(
        Conversation.objects.filter(
            space=space, platform=platform, source_conversation_id=name
        )[:2]
    )
    if len(rows) > 1:
        raise AmbiguousConversation
    row = rows[0] if rows else None
    if (
        row
        and row.source_namespace != account
        and account not in row.metadata.get("source_namespaces", [])
    ):
        row = None
    return row

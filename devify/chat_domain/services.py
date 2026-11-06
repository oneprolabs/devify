from dataclasses import dataclass
from urllib.parse import quote

from django.db import IntegrityError, transaction
from django.db.models import Count, Max

from chat_domain.models import (
    Conversation,
    Message,
    MessageOrigin,
    MessagePart,
)


@dataclass(frozen=True)
class ConversationResult:
    conversation: Conversation
    created: bool


@dataclass(frozen=True)
class MessageIngestResult:
    message: Message
    created: bool
    parts_created: int = 0
    origins_created: int = 0


def _clean(value):
    return (value or "").strip()


def build_identity_key(
    *,
    platform,
    source_namespace,
    source_conversation_id="",
    scope_key="",
):
    """Build the canonical conversation identity key.

    The source conversation id is authoritative. When the source has no
    stable conversation id, callers must pass a deterministic import scope
    key instead; a display title is never used as an identity.
    """
    platform = _clean(platform)
    namespace = _clean(source_namespace)
    conversation_id = _clean(source_conversation_id)
    scope = _clean(scope_key)
    if not platform or not namespace:
        raise ValueError("platform and source_namespace are required.")
    if not conversation_id and not scope:
        raise ValueError(
            "source_conversation_id or scope_key is required."
        )
    component = conversation_id or f"scope:{scope}"
    key = ":".join(
        quote(part, safe="")
        for part in (platform, namespace, component)
    )
    if len(key) > 700:
        raise ValueError("Conversation identity key is too long.")
    return key


def build_message_key(
    *,
    source_message_id="",
    revision="",
    record_locator_key="",
    file_sha256="",
):
    """Build the message idempotency key inside one conversation.

    Stable source ids include the source revision identifier. A source
    without ids only deduplicates retries of the same file, using the file
    hash plus the record locator.
    """
    source_id = _clean(source_message_id)
    revision = _clean(revision)
    if source_id:
        key = f"src:{quote(source_id, safe='')}"
        if revision:
            key = f"{key}@{quote(revision, safe='')}"
        return key
    locator = _clean(record_locator_key)
    digest = _clean(file_sha256)
    if not locator or not digest:
        raise ValueError(
            "Messages without a source id require record_locator_key "
            "and file_sha256."
        )
    return f"loc:{quote(digest, safe='')}#{quote(locator, safe='')}"


@transaction.atomic
def upsert_conversation(
    *,
    space,
    platform,
    source_namespace,
    source_conversation_id="",
    scope_key="",
    title="",
    kind=None,
    timezone="",
    self_sender_key="",
    metadata=None,
    identity_key=None,
):
    """Get or create the conversation for one source identity in a space.

    Re-imports update display-only fields (title, kind, timezone, metadata)
    but never create a second conversation for the same identity key.
    """
    key = identity_key or build_identity_key(
        platform=platform,
        source_namespace=source_namespace,
        source_conversation_id=source_conversation_id,
        scope_key=scope_key,
    )
    defaults = {
        "platform": platform,
        "source_namespace": source_namespace,
        "source_conversation_id": _clean(source_conversation_id),
        "title": _clean(title),
    }
    if kind:
        defaults["kind"] = kind
    if timezone:
        defaults["timezone"] = _clean(timezone)
    if self_sender_key:
        defaults["self_sender_key"] = _clean(self_sender_key)
    if metadata:
        defaults["metadata"] = dict(metadata)

    try:
        conversation, created = (
            Conversation.objects.select_for_update().get_or_create(
                space=space,
                identity_key=key,
                defaults=defaults,
            )
        )
    except IntegrityError:
        conversation = Conversation.objects.select_for_update().get(
            space=space,
            identity_key=key,
        )
        created = False

    if created:
        return ConversationResult(conversation=conversation, created=True)

    updates = {}
    if title and conversation.title != _clean(title):
        updates["title"] = _clean(title)
    if kind and kind != Conversation.Kind.UNKNOWN:
        if conversation.kind != kind:
            updates["kind"] = kind
    if timezone and conversation.timezone != _clean(timezone):
        updates["timezone"] = _clean(timezone)
    if self_sender_key:
        self_sender_key = _clean(self_sender_key)
        if conversation.self_sender_key != self_sender_key:
            updates["self_sender_key"] = self_sender_key
    if metadata:
        merged = {**(conversation.metadata or {}), **metadata}
        if merged != conversation.metadata:
            updates["metadata"] = merged
    if updates:
        for field, value in updates.items():
            setattr(conversation, field, value)
        updates["updated_at"] = None
        conversation.save(update_fields=tuple(updates))
    return ConversationResult(conversation=conversation, created=False)


@transaction.atomic
def upsert_message(
    *,
    conversation,
    message_key=None,
    source_message_id="",
    revision="",
    record_locator_key="",
    file_sha256="",
    record_kind=Message.RecordKind.MESSAGE,
    sender_key="",
    sender_name="",
    direction=Message.Direction.UNKNOWN,
    occurred_at=None,
    source_order=None,
    reply_to=None,
    target_source_id="",
    relation_kind="",
    source_fields=None,
    normalization_state=Message.NormalizationState.READY,
):
    """Get or create one message, deduplicating by (conversation, key).

    The conversation carries the space boundary, so the same source
    identity is deduplicated only inside one space.
    """
    key = message_key or build_message_key(
        source_message_id=source_message_id,
        revision=revision,
        record_locator_key=record_locator_key,
        file_sha256=file_sha256,
    )
    if len(key) > 500:
        raise ValueError("Message key is too long.")
    conversation = Conversation.objects.select_for_update().get(
        pk=conversation.pk
    )
    existing = Message.objects.filter(
        conversation=conversation,
        message_key=key,
    ).first()
    if existing:
        return existing, False
    if reply_to is not None and reply_to.conversation_id != conversation.pk:
        raise ValueError("reply_to must belong to the same conversation.")
    next_seq = (
        Message.objects.filter(conversation=conversation).aggregate(
            last=Max("ingest_seq")
        )["last"]
        or 0
    ) + 1
    try:
        with transaction.atomic():
            message = Message.objects.create(
                conversation=conversation,
                message_key=key,
                source_message_id=_clean(source_message_id),
                record_kind=record_kind,
                sender_key=_clean(sender_key),
                sender_name=_clean(sender_name),
                direction=direction,
                occurred_at=occurred_at,
                source_order=source_order,
                ingest_seq=next_seq,
                reply_to=reply_to,
                target_source_id=_clean(target_source_id),
                relation_kind=relation_kind,
                source_fields=dict(source_fields or {}),
                normalization_state=normalization_state,
            )
    except IntegrityError:
        message = Message.objects.get(
            conversation=conversation,
            message_key=key,
        )
        return message, False
    return message, True


def _ensure_part_parent(part, parent_part):
    seen = {part.pk}
    current = parent_part
    while current is not None:
        if current.pk in seen:
            raise ValueError("Message part hierarchy cannot contain cycles.")
        seen.add(current.pk)
        current = current.parent_part


@transaction.atomic
def upsert_message_part(
    *,
    message,
    part_key,
    kind,
    ordinal=0,
    text=None,
    parent_part=None,
    upload_item=None,
    binding_state=None,
    source_locator=None,
    source_header=None,
):
    """Get or create one message part, deduplicating by part key."""
    part_key = _clean(part_key)
    if not part_key:
        raise ValueError("part_key is required.")
    if parent_part is not None and parent_part.message_id != message.pk:
        raise ValueError("parent_part must belong to the same message.")
    part, created = MessagePart.objects.get_or_create(
        message=message,
        part_key=part_key,
        defaults={
            "kind": kind,
            "ordinal": ordinal,
            "text": text or "",
            "parent_part": parent_part,
            "upload_item": upload_item,
            "binding_state": (
                binding_state or MessagePart.BindingState.AVAILABLE
            ),
            "source_locator": dict(source_locator or {}),
            "source_header": dict(source_header or {}),
        },
    )
    if created:
        return part, True

    new_parent = parent_part if parent_part is not None else part.parent_part
    _ensure_part_parent(part, new_parent)

    values = {"kind": kind, "ordinal": ordinal}
    if text is not None:
        values["text"] = text
    if parent_part is not None:
        values["parent_part"] = parent_part
    if upload_item is not None:
        values["upload_item"] = upload_item
    if binding_state is not None:
        values["binding_state"] = binding_state
    if source_locator is not None:
        values["source_locator"] = dict(source_locator)
    if source_header is not None:
        values["source_header"] = dict(source_header)
    updates = {
        field: value
        for field, value in values.items()
        if getattr(part, field) != value
    }
    if not updates:
        return part, False
    for field, value in updates.items():
        setattr(part, field, value)
    updates["updated_at"] = None
    part.save(update_fields=tuple(updates))
    return part, False


@transaction.atomic
def record_message_origin(
    *,
    message,
    upload_item,
    locator_key,
    parser_version,
    record_locator=None,
):
    """Record one original file location for a message.

    Re-uploading the same range adds origins instead of messages. The same
    locator may not point at a different message for the same parser
    version.
    """
    locator_key = _clean(locator_key)
    parser_version = _clean(parser_version)
    if not locator_key or not parser_version:
        raise ValueError("locator_key and parser_version are required.")
    if upload_item.batch.space_id != message.conversation.space_id:
        raise ValueError("Message origin must belong to the same space.")
    origin, created = MessageOrigin.objects.get_or_create(
        upload_item=upload_item,
        locator_key=locator_key,
        parser_version=parser_version,
        defaults={
            "message": message,
            "record_locator": dict(record_locator or {}),
        },
    )
    if not created and origin.message_id != message.pk:
        raise ValueError(
            "Message origin already points at a different message."
        )
    return origin, created


def refresh_conversation_counters(conversation):
    """Recompute the derived message count and last message time."""
    summary = Message.objects.filter(conversation=conversation).aggregate(
        count=Count("id"),
        last=Max("occurred_at"),
    )
    message_count = summary["count"] or 0
    last_message_at = summary["last"]
    Conversation.objects.filter(pk=conversation.pk).update(
        message_count=message_count,
        last_message_at=last_message_at,
    )
    conversation.message_count = message_count
    conversation.last_message_at = last_message_at
    return conversation


@transaction.atomic
def ingest_message(*, conversation, parts=(), origin=None, **fields):
    """Store one normalized message with parts and its origin.

    Duplicate messages return the existing record and only append any new
    origins or parts, so repeated uploads stay idempotent.
    """
    message, created = upsert_message(
        conversation=conversation,
        **fields,
    )
    parts_created = 0
    for part in parts:
        _, part_created = upsert_message_part(message=message, **part)
        parts_created += int(part_created)
    origins_created = 0
    if origin:
        _, origin_created = record_message_origin(
            message=message,
            **origin,
        )
        origins_created += int(origin_created)
    if created:
        refresh_conversation_counters(conversation)
    return MessageIngestResult(
        message=message,
        created=created,
        parts_created=parts_created,
        origins_created=origins_created,
    )

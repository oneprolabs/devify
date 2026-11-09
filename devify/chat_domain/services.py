import hashlib
from dataclasses import dataclass
from urllib.parse import quote

from django.db import IntegrityError, transaction
from django.db.models import Count, Max

from chat_domain.models import (
    Conversation,
    Message,
    MessageAlias,
    MessageOrigin,
    MessagePart,
)

MEDIA_PART_KINDS = frozenset(
    {
        MessagePart.Kind.IMAGE,
        MessagePart.Kind.VIDEO,
        MessagePart.Kind.AUDIO,
        MessagePart.Kind.FILE,
    }
)
FINGERPRINT_VERSION = "fp.v1"


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
    source_namespace="",
    source_conversation_id="",
    scope_key="",
):
    """Build the canonical conversation identity key.

    The uploading account is deliberately absent from the key. Two people in
    one space exporting the same group must land on the same conversation;
    ``source_namespace`` stays in the signature for callers and older data,
    but it is stored as a source attribute instead of an identity.
    """
    platform = _clean(platform)
    conversation_id = _clean(source_conversation_id)
    scope = _clean(scope_key)
    if not platform:
        raise ValueError("platform is required.")
    if not conversation_id and not scope:
        raise ValueError("source_conversation_id or scope_key is required.")
    component = conversation_id or f"scope:{scope}"
    key = ":".join(
        quote(part, safe="") for part in (platform, component)
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


def message_fingerprint(
    *,
    occurred_at,
    sender_key,
    record_kind,
    parts,
):
    """Hash the portable content identity of one message.

    Local ids are per account and display names are per contact book, so
    neither can identify a message two people exported. Time, sender id, kind
    and the visible content can. Direction is excluded on purpose: the same
    message is outgoing for its author and incoming for everyone else.

    ``parts`` accepts mappings with ``kind``, ``ordinal``, ``text`` and
    ``media_sha256``. A message without a timestamp is never fingerprinted:
    guessing would merge unrelated messages.
    """
    if occurred_at is None:
        return ""
    ordered = sorted(
        parts,
        key=lambda part: (
            part.get("ordinal") or 0,
            part.get("part_key") or "",
        ),
    )
    texts = [
        part.get("text") or ""
        for part in ordered
        if part.get("kind") == MessagePart.Kind.TEXT
    ]
    media = [
        part.get("media_sha256") or ""
        for part in ordered
        if part.get("kind") in MEDIA_PART_KINDS
    ]
    if not any(texts) and not media:
        # A record with no visible content (a bare system line, for example)
        # carries nothing that distinguishes it from its neighbours in the
        # same second, so it must never be merged by fingerprint.
        return ""
    raw = "|".join(
        (
            FINGERPRINT_VERSION,
            str(int(occurred_at.timestamp())),
            _clean(sender_key),
            _clean(record_kind),
            "\n".join(texts),
            str(len(media)),
            "\n".join(media),
        )
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


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
        (
            conversation,
            created,
        ) = Conversation.objects.select_for_update().get_or_create(
            space=space,
            identity_key=key,
            defaults=defaults,
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
    namespace = _clean(source_namespace)
    if (
        namespace
        and conversation.source_namespace
        and namespace != conversation.source_namespace
    ):
        namespaces = list(
            (conversation.metadata or {}).get("source_namespaces") or []
        )
        for value in (conversation.source_namespace, namespace):
            if value not in namespaces:
                namespaces.append(value)
        merged = {**(updates.get("metadata") or conversation.metadata or {})}
        merged["source_namespaces"] = namespaces
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
    sequence_cache=None,
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
    # The parser holds the conversation lock for its enclosing transaction.
    if sequence_cache is not None and conversation.pk in sequence_cache:
        next_seq = sequence_cache[conversation.pk]
    else:
        next_seq = (
            Message.objects.filter(conversation=conversation).aggregate(
                last=Max("ingest_seq")
            )["last"] or 0
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
    if sequence_cache is not None:
        sequence_cache[conversation.pk] = next_seq + 1
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
    media_sha256=None,
    media_content_type=None,
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
            "media_sha256": media_sha256 or "",
            "media_content_type": media_content_type or "",
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
    if media_sha256:
        values["media_sha256"] = media_sha256
    if media_content_type:
        values["media_content_type"] = media_content_type
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
def ingest_message(
    *,
    conversation,
    parts=(),
    origin=None,
    source_namespace="",
    alias_key="",
    refresh_counters=True,
    **fields,
):
    """Store one normalized message with parts and its origin.

    Duplicate messages return the existing record and only append any new
    origins or parts, so repeated uploads stay idempotent. ``alias_key`` is
    the key this uploader used locally; when another account already created
    the same message under a different key, the alias resolves to it.
    """

    message = None
    created = False
    if alias_key and source_namespace:
        alias = (
            MessageAlias.objects.select_related("message")
            .filter(
                conversation=conversation,
                source_namespace=_clean(source_namespace),
                alias_key=_clean(alias_key),
            )
            .first()
        )
        if alias is not None:
            message = alias.message
    if message is None:
        message, created = upsert_message(
            conversation=conversation,
            **fields,
        )
    if alias_key and source_namespace and alias_key != message.message_key:
        MessageAlias.objects.get_or_create(
            conversation=conversation,
            source_namespace=_clean(source_namespace),
            alias_key=_clean(alias_key),
            defaults={"message": message},
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
    if message.orphaned_at is not None and message.origins.exists():
        # The message came back with a fresh upload: it may feed analysis
        # again even though the earlier contribution was withdrawn.
        message.orphaned_at = None
        message.save(update_fields=("orphaned_at", "updated_at"))
    if created and refresh_counters:
        refresh_conversation_counters(conversation)
    return MessageIngestResult(
        message=message,
        created=created,
        parts_created=parts_created,
        origins_created=origins_created,
    )


def set_message_fingerprint(message, fingerprint):
    if not fingerprint or message.content_fingerprint == fingerprint:
        return message
    message.content_fingerprint = fingerprint
    message.save(update_fields=("content_fingerprint", "updated_at"))
    return message


def apply_message_fingerprints(message_ids):
    """Compute the portable fingerprint for freshly parsed messages."""

    messages = Message.objects.filter(pk__in=message_ids).prefetch_related(
        "parts"
    )
    updated = 0
    for message in messages:
        parts = [
            {
                "kind": part.kind,
                "ordinal": part.ordinal,
                "part_key": part.part_key,
                "text": part.text,
                "media_sha256": part.media_sha256,
            }
            for part in message.parts.all()
        ]
        fingerprint = message_fingerprint(
            occurred_at=message.occurred_at,
            sender_key=message.sender_key,
            record_kind=message.record_kind,
            parts=parts,
        )
        if fingerprint:
            set_message_fingerprint(message, fingerprint)
            updated += 1
    return updated


@transaction.atomic
def merge_messages(*, source, target):
    """Fold one message row into another, keeping every source record.

    Only the duplicate message row disappears. Origins, parts, reply links
    and analysis evidence are re-pointed at the survivor, so a later upload
    by either account still finds the message and the space keeps a single
    copy of the content.
    """

    if source.pk == target.pk:
        return target

    Message.objects.filter(reply_to_id=source.pk).update(reply_to=target)
    MessageOrigin.objects.filter(message=source).update(message=target)

    for part in list(MessagePart.objects.filter(message=source)):
        existing = MessagePart.objects.filter(
            message=target, part_key=part.part_key
        ).first()
        if existing is None:
            part.message = target
            part.save(update_fields=("message", "updated_at"))
            continue
        updates = []
        if not existing.media_sha256 and part.media_sha256:
            existing.media_sha256 = part.media_sha256
            updates.append("media_sha256")
        if not existing.media_content_type and part.media_content_type:
            existing.media_content_type = part.media_content_type
            updates.append("media_content_type")
        if updates:
            existing.save(update_fields=(*updates, "updated_at"))
        part.delete()

    # Imported lazily: analysis depends on chat_domain, not the other way.
    from chat_analysis.models import EventEvidence, NoteEvidence

    for evidence in list(NoteEvidence.objects.filter(message=source)):
        if NoteEvidence.objects.filter(
            note_id=evidence.note_id, message=target
        ).exists():
            evidence.delete()
            continue
        evidence.message = target
        evidence.reference_key = NoteEvidence.build_reference_key(
            target.pk, evidence.message_part_id
        )
        if NoteEvidence.objects.filter(
            note_id=evidence.note_id, reference_key=evidence.reference_key
        ).exists():
            evidence.delete()
            continue
        evidence.save(
            update_fields=("message", "reference_key")
        )

    for evidence in list(EventEvidence.objects.filter(message=source)):
        EventEvidence.objects.get_or_create(
            event_id=evidence.event_id,
            message=target,
            defaults={"created_by_id": evidence.created_by_id},
        )
        evidence.delete()

    source.delete()
    return target


def consolidate_conversation_messages(conversation, *, fingerprints=None):
    """Merge messages of one conversation that share a fingerprint.

    Returns ``(source_id, target_id)`` pairs so the caller can tell how many
    rows this batch created that turned out to be duplicates.
    """

    query = Message.objects.filter(
        conversation=conversation
    ).exclude(content_fingerprint="")
    if fingerprints:
        query = query.filter(content_fingerprint__in=fingerprints)
    groups = list(
        query.values("content_fingerprint")
        .annotate(total=Count("id"))
        .filter(total__gt=1)
    )
    merges = []
    for group in groups:
        messages = list(
            Message.objects.filter(
                conversation=conversation,
                content_fingerprint=group["content_fingerprint"],
            ).order_by("id")
        )
        target = next(
            (
                message
                for message in messages
                if message.message_key.startswith("srv:")
            ),
            messages[0],
        )
        for source in messages:
            if source.pk == target.pk:
                continue
            source_id = source.pk
            merge_messages(source=source, target=target)
            merges.append((source_id, target.pk))
    if merges:
        refresh_conversation_counters(conversation)
    return merges

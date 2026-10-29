"""Persist a validated chat package into conversations and messages.

The package contract (zip safety, manifest and JSONL reading) lives in
``chat_ingestion.package``; this module only maps validated records onto
``chat_domain``. The target space and uploader always come from the
``UploadBatch`` and are never read from the package. A bad package is
rejected as a whole: the batch becomes ``failed`` and no conversation,
message or upload item is kept.
"""

import mimetypes
import zipfile
from dataclasses import dataclass
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db import transaction

from chat_domain.models import Conversation, Message, MessagePart
from chat_domain.services import (
    ingest_message,
    record_message_origin,
    upsert_conversation,
    upsert_message_part,
)
from chat_ingestion.models import UploadBatch, UploadItem
from chat_ingestion.package import (
    CONVERSATIONS_MEMBER,
    MESSAGES_MEMBER,
    ORIGINS_MEMBER,
    PARTS_MEMBER,
    ChatPackage,
    PackageError,
    normalize_member_path,
    parse_occurred_at,
)
from chat_ingestion.services import (
    UploadTransitionError,
    archive_path,
    transition_batch,
)

PARSER_VERSION = "wechat.v1"
EXPANDED_BYTES_SETTING = "CHAT_UPLOAD_MAX_EXPANDED_BYTES"
DEFAULT_MAX_EXPANDED_BYTES = 2 * 1024 * 1024 * 1024

_MEDIA_KINDS = frozenset(
    {
        MessagePart.Kind.IMAGE,
        MessagePart.Kind.VIDEO,
        MessagePart.Kind.AUDIO,
        MessagePart.Kind.FILE,
    }
)


class ArchiveParseError(ValueError):
    """The package violates the normalized archive contract."""


@dataclass(frozen=True)
class Manifest:
    platform: str
    source_namespace: str
    timezone: object
    conversation_ids: frozenset | None
    conversation_count: int
    message_count: int


def _where(name, line):
    return f"{name}:{line}"


def _string(record, key, where, *, max_length=255, required=False):
    value = record.get(key)
    if value is None:
        value = ""
    if not isinstance(value, str):
        raise ArchiveParseError(f"{where}: '{key}' must be a string.")
    if required and not value.strip():
        raise ArchiveParseError(f"{where}: '{key}' is required.")
    if len(value) > max_length:
        raise ArchiveParseError(
            f"{where}: '{key}' exceeds {max_length} characters."
        )
    return value


def _integer(record, key, where, *, minimum=0):
    value = record.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ArchiveParseError(f"{where}: '{key}' must be an integer.")
    if value < minimum:
        raise ArchiveParseError(
            f"{where}: '{key}' must be at least {minimum}."
        )
    return value


def _mapping(record, key, where):
    value = record.get(key)
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ArchiveParseError(f"{where}: '{key}' must be an object.")
    return value


def _choice(record, key, where, choices, default):
    value = record.get(key)
    if value in (None, ""):
        return default
    valid = {choice for choice, _ in choices}
    if value not in valid:
        raise ArchiveParseError(
            f"{where}: '{key}' has unsupported value {value!r}."
        )
    return value


def _timestamp(value, zone, where):
    if value in (None, ""):
        return None
    if not isinstance(value, str):
        raise ArchiveParseError(
            f"{where}: 'occurred_at' must be an ISO-8601 string."
        )
    try:
        return parse_occurred_at(value, zone)
    except ValueError as error:
        raise ArchiveParseError(f"{where}: {error}") from None


def _content_type(name):
    guessed, _ = mimetypes.guess_type(name)
    if guessed:
        return guessed
    if name.endswith(".jsonl"):
        return "application/x-ndjson"
    return "application/octet-stream"


def _max_expanded_bytes():
    value = getattr(settings, EXPANDED_BYTES_SETTING, None)
    if value is None:
        return DEFAULT_MAX_EXPANDED_BYTES
    return int(value)


def _item_for(items, path, where):
    if not path:
        return None
    try:
        name = normalize_member_path(path)
    except PackageError as error:
        raise ArchiveParseError(f"{where}: {error}") from None
    return items.get(name)


def _validate_manifest(package, batch):
    manifest = package.manifest

    if manifest.platform != batch.source_type:
        raise ArchiveParseError(
            "The archive platform does not match the upload batch."
        )
    if len(manifest.source_namespace) > 255:
        raise ArchiveParseError("'source_namespace' is too long.")

    counts = manifest.counts
    conversation_count = counts.get("conversations")
    message_count = counts.get("messages")
    if (
        isinstance(conversation_count, bool)
        or not isinstance(conversation_count, int)
        or conversation_count < 0
    ):
        raise ArchiveParseError("'counts.conversations' must be an integer.")
    if (
        isinstance(message_count, bool)
        or not isinstance(message_count, int)
        or message_count < 0
    ):
        raise ArchiveParseError("'counts.messages' must be an integer.")

    raw_ids = manifest.scope.get("conversation_ids")
    conversation_ids = None
    if raw_ids is not None:
        if not isinstance(raw_ids, list) or not all(
            isinstance(item, str) and item.strip() for item in raw_ids
        ):
            raise ArchiveParseError(
                "'scope.conversation_ids' must be a list of ids."
            )
        conversation_ids = frozenset(raw_ids)
        if manifest.whitelist and not conversation_ids.issubset(
            set(manifest.whitelist)
        ):
            raise ArchiveParseError(
                "The archive scope is not contained in its whitelist."
            )

    zone = manifest.tzinfo or ZoneInfo(settings.TIME_ZONE or "UTC")
    return Manifest(
        platform=manifest.platform,
        source_namespace=manifest.source_namespace,
        timezone=zone,
        conversation_ids=conversation_ids,
        conversation_count=conversation_count,
        message_count=message_count,
    )


def _parse_conversations(batch, manifest, package):
    conversations = {}
    declared = set()
    records = 0
    name = CONVERSATIONS_MEMBER

    for number, record in package.iter_jsonl(name):
        where = _where(name, number)
        records += 1
        source_id = _string(
            record, "conversation_id", where, max_length=255
        )
        scope_key = _string(record, "scope_key", where, max_length=255)
        if not source_id and not scope_key:
            raise ArchiveParseError(
                f"{where}: 'conversation_id' or 'scope_key' is required."
            )
        identity = source_id or scope_key
        if identity in declared:
            raise ArchiveParseError(
                f"{where}: duplicate conversation {identity!r}."
            )
        declared.add(identity)
        if (
            manifest.conversation_ids is not None
            and identity not in manifest.conversation_ids
        ):
            raise ArchiveParseError(
                f"{where}: conversation {identity!r} is outside the "
                "declared scope."
            )

        title = _string(record, "title", where, max_length=500)
        kind = _choice(
            record,
            "kind",
            where,
            Conversation.Kind.choices,
            Conversation.Kind.UNKNOWN,
        )
        timezone_name = _string(record, "timezone", where, max_length=64)
        self_sender_key = _string(
            record, "self_sender_key", where, max_length=255
        )
        metadata = _mapping(record, "metadata", where)

        result = upsert_conversation(
            space=batch.space,
            platform=manifest.platform,
            source_namespace=manifest.source_namespace,
            source_conversation_id=source_id,
            scope_key=scope_key,
            title=title,
            kind=kind,
            timezone=timezone_name,
            self_sender_key=self_sender_key,
            metadata=metadata,
        )
        conversations[identity] = result.conversation
        if scope_key and scope_key not in conversations:
            conversations[scope_key] = result.conversation

    if records != manifest.conversation_count:
        raise ArchiveParseError(
            f"{name}: manifest counts {manifest.conversation_count} "
            f"conversations but the archive contains {records}."
        )
    if (
        manifest.conversation_ids is not None
        and declared != manifest.conversation_ids
    ):
        raise ArchiveParseError(
            "The archive conversations do not match the declared scope."
        )
    return conversations


def _conversation(conversations, record, where):
    source_id = _string(record, "conversation_id", where, max_length=255)
    if not source_id:
        raise ArchiveParseError(
            f"{where}: 'conversation_id' is required."
        )
    conversation = conversations.get(source_id)
    if conversation is None:
        raise ArchiveParseError(
            f"{where}: unknown conversation {source_id!r}."
        )
    return conversation


def _parse_messages(
    manifest, package, conversations, message_digest, message_item
):
    messages = {}
    created_count = 0
    duplicate_count = 0
    records = 0
    name = MESSAGES_MEMBER

    for number, record in package.iter_jsonl(name):
        where = _where(name, number)
        records += 1
        conversation = _conversation(conversations, record, where)

        message_key = _string(record, "message_key", where, max_length=500)
        source_message_id = _string(
            record, "source_message_id", where, max_length=255
        )
        revision = _string(record, "revision", where, max_length=100)
        locator_key = _string(
            record, "record_locator_key", where, max_length=255
        )
        if not message_key and not source_message_id and not locator_key:
            locator_key = f"line:{number}"

        occurred_at = _timestamp(
            record.get("occurred_at"), manifest.timezone, where
        )
        source_order = _integer(record, "source_order", where)
        source_fields = _mapping(record, "source_fields", where)

        result = ingest_message(
            conversation=conversation,
            message_key=message_key or None,
            source_message_id=source_message_id,
            revision=revision,
            record_locator_key=locator_key,
            file_sha256=message_digest,
            record_kind=_choice(
                record,
                "record_kind",
                where,
                Message.RecordKind.choices,
                Message.RecordKind.MESSAGE,
            ),
            sender_key=_string(record, "sender_key", where, max_length=255),
            sender_name=_string(
                record, "sender_name", where, max_length=255
            ),
            direction=_choice(
                record,
                "direction",
                where,
                Message.Direction.choices,
                Message.Direction.UNKNOWN,
            ),
            occurred_at=occurred_at,
            source_order=source_order,
            target_source_id=_string(
                record, "target_source_id", where, max_length=255
            ),
            relation_kind=_choice(
                record,
                "relation_kind",
                where,
                Message.RelationKind.choices,
                "",
            ),
            source_fields=source_fields,
            normalization_state=_choice(
                record,
                "normalization_state",
                where,
                Message.NormalizationState.choices,
                Message.NormalizationState.READY,
            ),
            origin={
                "upload_item": message_item,
                "locator_key": f"line:{number}",
                "parser_version": PARSER_VERSION,
                "record_locator": {"file": name, "line": number},
            },
        )
        canonical_key = result.message.message_key
        messages[(conversation.pk, canonical_key)] = result.message
        if message_key:
            messages[(conversation.pk, message_key)] = result.message
        if result.created:
            created_count += 1
        else:
            duplicate_count += 1

    if records != manifest.message_count:
        raise ArchiveParseError(
            f"{name}: manifest counts {manifest.message_count} messages "
            f"but the archive contains {records}."
        )
    return messages, created_count, duplicate_count


def _message(messages, conversation, record, where):
    message_key = _string(record, "message_key", where, max_length=500)
    if not message_key:
        raise ArchiveParseError(f"{where}: 'message_key' is required.")
    message = messages.get((conversation.pk, message_key))
    if message is None:
        raise ArchiveParseError(
            f"{where}: unknown message {message_key!r}."
        )
    return message


def _parse_parts(package, conversations, messages, items):
    if not package.has(PARTS_MEMBER):
        return
    parts = {}
    name = PARTS_MEMBER
    for number, record in package.iter_jsonl(name):
        where = _where(name, number)
        conversation = _conversation(conversations, record, where)
        message = _message(messages, conversation, record, where)

        part_key = _string(
            record, "part_key", where, max_length=255, required=True
        )
        kind = _choice(
            record,
            "kind",
            where,
            MessagePart.Kind.choices,
            MessagePart.Kind.UNKNOWN,
        )
        ordinal = _integer(record, "ordinal", where) or 0

        parent_key = _string(
            record, "parent_part_key", where, max_length=255
        )
        parent = None
        if parent_key:
            parent = parts.get((message.pk, parent_key))
            if parent is None:
                raise ArchiveParseError(
                    f"{where}: parent part {parent_key!r} must appear "
                    "before its child."
                )

        upload_item_path = _string(
            record, "upload_item_path", where, max_length=500
        )
        upload_item = _item_for(items, upload_item_path, where)

        supplied_state = _choice(
            record,
            "binding_state",
            where,
            MessagePart.BindingState.choices,
            "",
        )
        if supplied_state:
            binding_state = supplied_state
        elif upload_item is not None:
            binding_state = MessagePart.BindingState.AVAILABLE
        elif kind in _MEDIA_KINDS:
            binding_state = MessagePart.BindingState.MISSING
        else:
            binding_state = MessagePart.BindingState.AVAILABLE

        part, _ = upsert_message_part(
            message=message,
            part_key=part_key,
            kind=kind,
            ordinal=ordinal,
            text=_string(record, "text", where, max_length=1024 * 1024),
            parent_part=parent,
            upload_item=upload_item,
            binding_state=binding_state,
            source_locator=_mapping(record, "source_locator", where),
            source_header=_mapping(record, "source_header", where),
        )
        parts[(message.pk, part.part_key)] = part


def _parse_origins(package, conversations, messages, items):
    if not package.has(ORIGINS_MEMBER):
        return
    name = ORIGINS_MEMBER
    for number, record in package.iter_jsonl(name):
        where = _where(name, number)
        conversation = _conversation(conversations, record, where)
        message = _message(messages, conversation, record, where)

        locator_key = _string(
            record, "locator_key", where, max_length=255, required=True
        )
        parser_version = _string(
            record, "parser_version", where, max_length=50
        ) or PARSER_VERSION
        upload_item_path = _string(
            record, "upload_item_path", where, max_length=500
        )
        if upload_item_path:
            upload_item = _item_for(items, upload_item_path, where)
        else:
            upload_item = items.get(MESSAGES_MEMBER)
        if upload_item is None:
            raise ArchiveParseError(
                f"{where}: origin file is not part of the archive."
            )
        record_message_origin(
            message=message,
            upload_item=upload_item,
            locator_key=locator_key,
            parser_version=parser_version,
            record_locator=_mapping(record, "record_locator", where),
        )


@transaction.atomic
def _parse_locked(batch):
    path = archive_path(batch)
    if not path.is_file():
        raise ArchiveParseError("The stored archive is missing.")

    with ChatPackage(path) as package:
        manifest = _validate_manifest(package, batch)

        items = {}
        expanded = 0
        limit = _max_expanded_bytes()
        for name in package.member_names():
            sha256, size = package.digest(name)
            expanded += size
            if expanded > limit:
                raise ArchiveParseError(
                    "The expanded archive exceeds the allowed size."
                )
            item, _ = UploadItem.objects.update_or_create(
                batch=batch,
                path=name,
                defaults={
                    "content_type": _content_type(name),
                    "size": size,
                    "sha256": sha256,
                    "status": UploadItem.Status.ACCEPTED,
                    "message_count": 0,
                    "error_message": "",
                },
            )
            items[name] = item

        conversations = _parse_conversations(batch, manifest, package)
        messages, created_count, duplicate_count = _parse_messages(
            manifest,
            package,
            conversations,
            items[MESSAGES_MEMBER].sha256,
            items[MESSAGES_MEMBER],
        )
        _parse_parts(package, conversations, messages, items)
        _parse_origins(package, conversations, messages, items)

    message_item = items[MESSAGES_MEMBER]
    message_item.message_count = created_count
    if created_count == 0 and duplicate_count:
        message_item.status = UploadItem.Status.DUPLICATE
    message_item.save(
        update_fields=("message_count", "status", "updated_at")
    )

    batch.message_count = created_count
    batch.duplicate_count = duplicate_count
    batch.save(
        update_fields=("message_count", "duplicate_count", "updated_at")
    )
    transition_batch(batch, UploadBatch.Status.COMPLETED, error_message="")


def parse_archive(batch):
    """Parse a stored archive and move the batch to completed or failed.

    The caller is expected to have moved the batch to ``processing`` (the
    complete endpoint does this). Any contract violation rolls back all
    parsed rows and records the failure on the batch instead.
    """

    with transaction.atomic():
        batch = UploadBatch.objects.select_for_update().get(pk=batch.pk)
        if batch.status != UploadBatch.Status.PROCESSING:
            raise UploadTransitionError(
                "Only a processing upload can be parsed."
            )
        try:
            _parse_locked(batch)
        except (
            ArchiveParseError,
            PackageError,
            RuntimeError,
            UnicodeDecodeError,
            zipfile.BadZipFile,
            OSError,
        ) as error:
            batch.refresh_from_db(fields=("status", "error_message"))
            if batch.status == UploadBatch.Status.PROCESSING:
                message = str(error) or error.__class__.__name__
                transition_batch(
                    batch,
                    UploadBatch.Status.FAILED,
                    error_message=message,
                )
        return batch

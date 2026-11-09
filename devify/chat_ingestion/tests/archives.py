"""Builders for normalized chat archives used by upload/parse tests."""

import io
import json
import zipfile

SCHEMA_VERSION = "wechat.v1"


def default_manifest(conversations, messages, **overrides):
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "platform": "wechat",
        "source_namespace": "account:local-account-1",
        "timezone": "Asia/Shanghai",
        "scope": {"conversation_ids": ["group-a"]},
        "whitelist_snapshot": ["group-a", "group-b"],
        "counts": {
            "conversations": conversations,
            "messages": messages,
        },
        "client": {"name": "Wechatify", "version": "0.0.1"},
    }
    manifest.update(overrides)
    return manifest


DEFAULT_CONVERSATIONS = [
    {
        "conversation_id": "group-a",
        "title": "项目群",
        "kind": "group",
        "timezone": "Asia/Shanghai",
        "self_sender_key": "wx-self",
    }
]

DEFAULT_MESSAGES = [
    {
        "conversation_id": "group-a",
        "message_key": "srv:1",
        "source_message_id": "1",
        "sender_key": "wx-a",
        "sender_name": "甲",
        "direction": "incoming",
        "occurred_at": "2026-10-20T09:00:00+08:00",
        "source_order": 1,
        "source_fields": {"msg_type": 1},
    },
    {
        "conversation_id": "group-a",
        "message_key": "srv:2",
        "source_message_id": "2",
        "sender_key": "wx-self",
        "sender_name": "我",
        "direction": "outgoing",
        "occurred_at": "2026-10-20T09:05:00+08:00",
        "source_order": 2,
        "source_fields": {"msg_type": 3},
    },
]

DEFAULT_PARTS = [
    {
        "conversation_id": "group-a",
        "message_key": "srv:1",
        "part_key": "p0",
        "kind": "text",
        "ordinal": 0,
        "text": "早上好",
        "source_locator": {"json_pointer": "/items/0/content/Text"},
    },
    {
        "conversation_id": "group-a",
        "message_key": "srv:2",
        "part_key": "p0",
        "kind": "image",
        "ordinal": 0,
        "upload_item_path": "media/photo.png",
        "source_locator": {"json_pointer": "/items/1/content/Image"},
    },
]

DEFAULT_MEDIA = {"media/photo.png": b"\x89PNG\r\n\x1a\nphoto"}


def _jsonl(records):
    return "".join(
        json.dumps(record, ensure_ascii=False) + "\n" for record in records
    )


def build_archive(
    *,
    manifest=None,
    conversations=None,
    messages=None,
    parts=None,
    origins=None,
    media=None,
    extra=None,
    omit=(),
):
    conversations = (
        DEFAULT_CONVERSATIONS if conversations is None else conversations
    )
    messages = DEFAULT_MESSAGES if messages is None else messages
    parts = DEFAULT_PARTS if parts is None else parts
    origins = [] if origins is None else origins
    media = DEFAULT_MEDIA if media is None else media
    if manifest is None:
        manifest = default_manifest(len(conversations), len(messages))

    files = {
        "manifest.json": json.dumps(manifest, ensure_ascii=False),
        "conversations.jsonl": _jsonl(conversations),
        "messages.jsonl": _jsonl(messages),
        "message_parts.jsonl": _jsonl(parts),
        "origins.jsonl": _jsonl(origins),
    }
    files.update(media)
    if extra:
        files.update(extra)
    for name in omit:
        files.pop(name, None)

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return buffer.getvalue()

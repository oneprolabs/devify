"""Negative cases for the ``wechat.v1`` archive contract itself.

These exercise ``chat_ingestion.package`` directly: unsafe members, manifest
validation and JSONL limits. Parse-level negatives live in ``test_parsing``.
"""

import io
import json
import zipfile

import pytest

from chat_ingestion.package import (
    ChatPackage,
    ManifestInvalid,
    PackageInvalid,
    normalize_member_path,
    parse_occurred_at,
)
from chat_ingestion.tests.archives import (
    DEFAULT_CONVERSATIONS,
    build_archive,
    default_manifest,
)

pytestmark = pytest.mark.django_db


def write_package(tmp_path, content, name="package.zip"):
    path = tmp_path / name
    path.write_bytes(content)
    return path


def raw_zip(entries):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries:
            archive.writestr(name, content)
    return buffer.getvalue()


@pytest.mark.parametrize(
    "name",
    [
        "/etc/passwd",
        "../escape.jsonl",
        "./messages.jsonl",
        "a\\b.jsonl",
        "",
        "a\x00b",
    ],
)
def test_unsafe_member_paths_are_rejected(name):
    with pytest.raises(PackageInvalid):
        normalize_member_path(name)


def test_symlink_member_is_rejected(tmp_path):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("manifest.json", "{}")
        info = zipfile.ZipInfo("conversations.jsonl")
        info.external_attr = (0o120777 << 16) | 0o777
        archive.writestr(info, "")
        archive.writestr("messages.jsonl", "")
    path = write_package(tmp_path, buffer.getvalue())

    with pytest.raises(PackageInvalid, match="symlink"):
        ChatPackage(path)


def test_duplicate_member_is_rejected(tmp_path):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("manifest.json", "{}")
        archive.writestr("conversations.jsonl", "")
        archive.writestr("messages.jsonl", "")
        archive.writestr("messages.jsonl", "")
    path = write_package(tmp_path, buffer.getvalue())

    with pytest.raises(PackageInvalid, match="Duplicate archive member"):
        ChatPackage(path)


def test_missing_required_member_is_rejected(tmp_path):
    content = build_archive(omit=("messages.jsonl",))
    with pytest.raises(
        PackageInvalid, match="Missing required archive member"
    ):
        ChatPackage(write_package(tmp_path, content))


def test_member_and_total_size_limits_are_enforced(tmp_path, settings):
    settings.CHAT_IMPORT_MAX_FILE_BYTES = 16
    content = build_archive()
    with pytest.raises(PackageInvalid, match="too large"):
        ChatPackage(write_package(tmp_path, content))

    settings.CHAT_IMPORT_MAX_FILE_BYTES = 1024 * 1024
    settings.CHAT_IMPORT_MAX_TOTAL_BYTES = 64
    with pytest.raises(PackageInvalid, match="larger than the import limit"):
        ChatPackage(write_package(tmp_path, content))


def test_member_count_limit_is_enforced(tmp_path, settings):
    settings.CHAT_IMPORT_MAX_MEMBERS = 2
    with pytest.raises(PackageInvalid, match="too many files"):
        ChatPackage(write_package(tmp_path, build_archive()))


def test_unreadable_archive_is_rejected(tmp_path):
    path = write_package(tmp_path, b"not a zip file")
    with pytest.raises(PackageInvalid, match="cannot be opened"):
        ChatPackage(path)


@pytest.mark.parametrize(
    "manifest, message",
    [
        ("not json", "not valid JSON"),
        ("[]", "must be a JSON object"),
        ({}, "requires a schema_version"),
        (
            {"schema_version": "wechat.v1", "platform": "wechat"},
            "requires a source_namespace",
        ),
        (
            {
                "schema_version": "wechat.v1",
                "platform": "signal",
                "source_namespace": "ns",
            },
            "unsupported platform",
        ),
        (
            {
                "schema_version": "wechat.v2",
                "platform": "wechat",
                "source_namespace": "ns",
            },
            "does not match the platform",
        ),
        (
            {
                "schema_version": "wechat.v1",
                "platform": "wechat",
                "source_namespace": "ns",
                "scope": [],
            },
            "scope must be an object",
        ),
        (
            {
                "schema_version": "wechat.v1",
                "platform": "wechat",
                "source_namespace": "ns",
                "counts": [],
            },
            "counts must be an object",
        ),
        (
            {
                "schema_version": "wechat.v1",
                "platform": "wechat",
                "source_namespace": "ns",
                "whitelist_snapshot": [1, 2],
            },
            "list of strings",
        ),
        (
            {
                "schema_version": "wechat.v1",
                "platform": "wechat",
                "source_namespace": "ns",
                "timezone": "Mars/Olympus",
            },
            "unknown timezone",
        ),
    ],
)
def test_manifest_validation_rejects_broken_input(tmp_path, manifest, message):
    raw = manifest if isinstance(manifest, str) else json.dumps(manifest)
    content = raw_zip(
        [
            ("manifest.json", raw),
            ("conversations.jsonl", ""),
            ("messages.jsonl", ""),
        ]
    )
    with pytest.raises(ManifestInvalid, match=message):
        ChatPackage(write_package(tmp_path, content)).manifest


def test_manifest_requires_a_valid_json_object_file(tmp_path):
    content = raw_zip(
        [
            ("manifest.json", json.dumps(default_manifest(0, 0))),
            ("conversations.jsonl", ""),
            ("messages.jsonl", ""),
        ]
    )
    package = ChatPackage(write_package(tmp_path, content))
    assert package.manifest.platform == "wechat"
    assert package.manifest.tzinfo is not None
    assert package.manifest.whitelist == ("group-a", "group-b")


def test_jsonl_rejects_invalid_json_and_non_object_lines(tmp_path):
    manifest = default_manifest(1, 1)
    for line, message in (
        ('{"conversation_id":', "not valid JSON"),
        ("[1]", "must be a JSON object"),
    ):
        content = raw_zip(
            [
                ("manifest.json", json.dumps(manifest)),
                ("conversations.jsonl", line + "\n"),
                ("messages.jsonl", ""),
            ]
        )
        with pytest.raises(PackageInvalid, match=message):
            list(
                ChatPackage(write_package(tmp_path, content)).iter_jsonl(
                    "conversations.jsonl"
                )
            )


def test_jsonl_record_limit_is_enforced(tmp_path, settings):
    settings.CHAT_IMPORT_MAX_RECORDS = 1
    content = raw_zip(
        [
            ("manifest.json", json.dumps(default_manifest(2, 0))),
            (
                "conversations.jsonl",
                "\n".join(
                    json.dumps(item) for item in DEFAULT_CONVERSATIONS * 2
                ),
            ),
            ("messages.jsonl", ""),
        ]
    )
    with pytest.raises(PackageInvalid, match="too many records"):
        list(
            ChatPackage(write_package(tmp_path, content)).iter_jsonl(
                "conversations.jsonl"
            )
        )


@pytest.mark.parametrize(
    "value, message",
    [
        ("", "occurred_at is required"),
        ("not-a-time", "not an ISO timestamp"),
        ("2026-10-20T09:00:00", "has no timezone"),
    ],
)
def test_occurred_at_requires_an_absolute_timestamp(value, message):
    with pytest.raises(ValueError, match=message):
        parse_occurred_at(value, None)

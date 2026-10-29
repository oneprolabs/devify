"""Reading and validating a normalized chat upload package.

The package is a zip archive produced by the desktop client:

    manifest.json
    conversations.jsonl
    messages.jsonl
    message_parts.jsonl   # optional
    origins.jsonl         # optional
    media/...             # optional

Every member name is untrusted input: paths are rejected when absolute, when
they escape the archive root, or when they are symlinks. Sizes are checked
both from the central directory and while streaming.
"""

import hashlib
import io
import json
import zipfile
from dataclasses import dataclass, field
from datetime import timezone as dt_timezone
from pathlib import Path, PurePosixPath
from zoneinfo import ZoneInfo

from django.conf import settings
from django.utils.dateparse import parse_datetime

MANIFEST_MEMBER = "manifest.json"
CONVERSATIONS_MEMBER = "conversations.jsonl"
MESSAGES_MEMBER = "messages.jsonl"
PARTS_MEMBER = "message_parts.jsonl"
ORIGINS_MEMBER = "origins.jsonl"
REQUIRED_MEMBERS = (MANIFEST_MEMBER, CONVERSATIONS_MEMBER, MESSAGES_MEMBER)
SUPPORTED_PLATFORMS = ("wechat", "whatsapp", "line")
JSONL_MEMBERS = (
    CONVERSATIONS_MEMBER,
    MESSAGES_MEMBER,
    PARTS_MEMBER,
    ORIGINS_MEMBER,
)

MANIFEST_MAX_BYTES = 2 * 1024 * 1024
CHUNK_SIZE = 1024 * 1024


class PackageError(ValueError):
    """Base class for invalid upload packages."""


class PackageInvalid(PackageError):
    """The archive itself is unsafe, incomplete or unreadable."""


class ManifestInvalid(PackageError):
    """The manifest is missing required information or is inconsistent."""


def _setting(name, default):
    return getattr(settings, name, default)


def max_members():
    return int(_setting("CHAT_IMPORT_MAX_MEMBERS", 5000))


def max_member_bytes():
    return int(_setting("CHAT_IMPORT_MAX_FILE_BYTES", 256 * 1024 * 1024))


def max_total_bytes():
    return int(_setting("CHAT_IMPORT_MAX_TOTAL_BYTES", 2 * 1024 * 1024 * 1024))


def max_records():
    return int(_setting("CHAT_IMPORT_MAX_RECORDS", 50000))


@dataclass(frozen=True)
class PackageManifest:
    schema_version: str
    platform: str
    source_namespace: str
    timezone: str = ""
    tzinfo: object = None
    scope: dict = field(default_factory=dict)
    counts: dict = field(default_factory=dict)
    whitelist: tuple = ()

    @property
    def parser_version(self):
        return self.schema_version

    @property
    def scope_conversation_ids(self):
        values = self.scope.get("conversation_ids") or []
        if not isinstance(values, list):
            raise ManifestInvalid(
                "manifest.json scope.conversation_ids must be a list."
            )
        return tuple(str(value) for value in values)


def normalize_member_path(name):
    """Return a normalized archive-relative POSIX path or raise."""
    text = str(name or "").strip()
    if not text or "\x00" in text or "\\" in text:
        raise PackageInvalid(f"Unsafe archive member path: {name!r}.")
    pure = PurePosixPath(text)
    if pure.is_absolute() or ".." in pure.parts or text.startswith("./"):
        raise PackageInvalid(f"Unsafe archive member path: {name!r}.")
    return pure.as_posix()


def _is_symlink(info):
    return (info.external_attr >> 16) & 0o170000 == 0o120000


class ChatPackage:
    """A validated, read-only view over one uploaded archive."""

    def __init__(self, path):
        self.path = Path(path)
        try:
            self._zip = zipfile.ZipFile(self.path)
        except (OSError, zipfile.BadZipFile) as error:
            raise PackageInvalid(
                f"The archive cannot be opened: {error}."
            ) from error
        self._members = {}
        self._manifest = None
        try:
            self._validate_members()
        except Exception:
            self._zip.close()
            raise

    def close(self):
        self._zip.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.close()
        return False

    def _validate_members(self):
        total = 0
        for info in self._zip.infolist():
            if info.is_dir():
                continue
            name = normalize_member_path(info.filename)
            if _is_symlink(info):
                raise PackageInvalid(
                    f"Archive member is a symlink: {name!r}."
                )
            if name in self._members:
                raise PackageInvalid(
                    f"Duplicate archive member: {name!r}."
                )
            if info.file_size > max_member_bytes():
                raise PackageInvalid(
                    f"Archive member is too large: {name!r}."
                )
            total += info.file_size
            self._members[name] = info
        if total > max_total_bytes():
            raise PackageInvalid(
                "The archive is larger than the import limit."
            )
        if len(self._members) > max_members():
            raise PackageInvalid(
                "The archive contains too many files for one import."
            )
        for required in REQUIRED_MEMBERS:
            if required not in self._members:
                raise PackageInvalid(
                    f"Missing required archive member: {required}."
                )

    def member_names(self):
        return sorted(self._members)

    def has(self, name):
        try:
            return normalize_member_path(name) in self._members
        except PackageInvalid:
            return False

    def read_bytes(self, name, limit=None):
        if name not in self._members:
            raise PackageInvalid(f"Missing archive member: {name}.")
        limit = limit or max_member_bytes()
        with self._zip.open(name) as handle:
            data = handle.read(limit + 1)
        if len(data) > limit:
            raise PackageInvalid(f"Archive member is too large: {name!r}.")
        return data

    def digest(self, name):
        """Stream one member and return ``(sha256_hex, size_bytes)``."""
        if name not in self._members:
            raise PackageInvalid(f"Missing archive member: {name}.")
        digest = hashlib.sha256()
        size = 0
        limit = max_member_bytes()
        with self._zip.open(name) as handle:
            while True:
                chunk = handle.read(CHUNK_SIZE)
                if not chunk:
                    break
                size += len(chunk)
                if size > limit:
                    raise PackageInvalid(
                        f"Archive member is too large: {name!r}."
                    )
                digest.update(chunk)
        return digest.hexdigest(), size

    def iter_jsonl(self, name):
        """Yield ``(line_number, record)`` for one JSONL member."""
        if name not in self._members:
            return
        seen = 0
        with self._zip.open(name) as raw:
            stream = io.TextIOWrapper(raw, encoding="utf-8-sig")
            for line_number, line in enumerate(stream, start=1):
                text = line.strip()
                if not text:
                    continue
                seen += 1
                if seen > max_records():
                    raise PackageInvalid(
                        f"{name} contains too many records for one import."
                    )
                try:
                    record = json.loads(text)
                except json.JSONDecodeError as error:
                    raise PackageInvalid(
                        f"{name} line {line_number} is not valid JSON."
                    ) from error
                if not isinstance(record, dict):
                    raise PackageInvalid(
                        f"{name} line {line_number} must be a JSON object."
                    )
                yield line_number, record

    @property
    def manifest(self):
        if self._manifest is None:
            self._manifest = self._read_manifest()
        return self._manifest

    def _read_manifest(self):
        data = self.read_bytes(MANIFEST_MEMBER, limit=MANIFEST_MAX_BYTES)
        try:
            payload = json.loads(data.decode("utf-8-sig"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ManifestInvalid(
                "manifest.json is not valid JSON."
            ) from error
        if not isinstance(payload, dict):
            raise ManifestInvalid("manifest.json must be a JSON object.")
        schema_version = str(payload.get("schema_version") or "").strip()
        platform = str(payload.get("platform") or "").strip().lower()
        namespace = str(payload.get("source_namespace") or "").strip()
        timezone = str(payload.get("timezone") or "").strip()
        if not schema_version:
            raise ManifestInvalid(
                "manifest.json requires a schema_version."
            )
        if platform not in SUPPORTED_PLATFORMS:
            raise ManifestInvalid(
                "manifest.json has an unsupported platform."
            )
        if schema_version != f"{platform}.v1":
            raise ManifestInvalid(
                "manifest.json schema_version does not match the platform."
            )
        if not namespace:
            raise ManifestInvalid(
                "manifest.json requires a source_namespace."
            )
        tzinfo = None
        if timezone:
            try:
                tzinfo = ZoneInfo(timezone)
            except (KeyError, ValueError) as error:
                raise ManifestInvalid(
                    f"manifest.json has an unknown timezone: {timezone!r}."
                ) from error
        scope = payload.get("scope") or {}
        if not isinstance(scope, dict):
            raise ManifestInvalid("manifest.json scope must be an object.")
        counts = payload.get("counts") or {}
        if not isinstance(counts, dict):
            raise ManifestInvalid("manifest.json counts must be an object.")
        whitelist = payload.get("whitelist_snapshot") or []
        if not isinstance(whitelist, list) or not all(
            isinstance(value, str) for value in whitelist
        ):
            raise ManifestInvalid(
                "manifest.json whitelist_snapshot must be a list of strings."
            )
        return PackageManifest(
            schema_version=schema_version,
            platform=platform,
            source_namespace=namespace,
            timezone=timezone,
            tzinfo=tzinfo,
            scope=scope,
            counts=counts,
            whitelist=tuple(whitelist),
        )


def parse_occurred_at(value, tzinfo, timezone_name=""):
    """Parse an ISO timestamp, interpreting naive values in the source tz."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError("occurred_at is required.")
    parsed = parse_datetime(value.strip())
    if parsed is None:
        raise ValueError(f"occurred_at is not an ISO timestamp: {value!r}.")
    if parsed.tzinfo is None:
        if tzinfo is None:
            raise ValueError(
                "occurred_at has no timezone and the manifest has none "
                "either."
            )
        parsed = parsed.replace(tzinfo=tzinfo)
    return parsed.astimezone(dt_timezone.utc)


def parse_int(value, *, field_name, default=None, minimum=None):
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be an integer.")
    try:
        number = int(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{field_name} must be an integer.") from error
    if minimum is not None and number < minimum:
        raise ValueError(f"{field_name} must be >= {minimum}.")
    return number

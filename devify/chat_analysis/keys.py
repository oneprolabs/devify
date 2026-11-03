"""Stable keys for chat analysis resources.

Event keys come from an LLM, so the same matter can arrive as
``evt_inc13442_hcs_block_storage`` in one chunk and
``INC13442-2026-08-12`` in the next. Canonicalising the key on the server is
what lets ``Event`` stay one row per matter instead of one row per extraction.
"""

import re
import unicodedata

_SEPARATORS = re.compile(r"[^0-9a-z\u4e00-\u9fff]+")
_REPEATED_DASHES = re.compile(r"-{2,}")
_PREFIXES = re.compile(r"^(?:evt|event|e)[-_]+")
_DATE_TOKEN = re.compile(
    r"(?<![0-9a-z])"
    r"(?:(?:19|20)\d{2}[-_]?\d{2}[-_]?\d{2}|(?:19|20)\d{6})"
    r"(?![0-9a-z])"
)
_INCIDENT = re.compile(r"\b(?:inc|case|ticket)[-_ ]?(\d{3,})\b", re.IGNORECASE)
_MAX_KEY_LENGTH = 200


def slugify_key(value, *, limit=_MAX_KEY_LENGTH):
    """Normalise arbitrary text into a lowercase dash-separated key."""
    text = unicodedata.normalize("NFKC", str(value or "")).strip().lower()
    text = _SEPARATORS.sub("-", text)
    text = _REPEATED_DASHES.sub("-", text)
    return text.strip("-")[:limit].strip("-")


def canonical_event_key(raw_key, *, title=""):
    """Return a stable key for an event.

    Dates and extractor-specific prefixes are dropped because they change on
    every run, while the matter itself does not. The title is only used when
    the raw key carries no usable token.
    """
    key = slugify_key(raw_key)
    while _PREFIXES.match(key):
        key = _PREFIXES.sub("", key)
    key = _DATE_TOKEN.sub("-", key)
    key = slugify_key(key)
    if key:
        return key
    return slugify_key(title)


def canonical_entity_key(value):
    """Return a grouping key such as ``inc14419`` or ``antel``."""
    return slugify_key(value, limit=80)


def entity_from_text(*values):
    """Derive an entity key from free text, e.g. an INC number in a title."""
    for value in values:
        match = _INCIDENT.search(str(value or ""))
        if match:
            return f"inc{match.group(1)}"
    return ""

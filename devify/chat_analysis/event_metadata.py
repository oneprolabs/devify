"""Keep chat participants out of extracted matter titles and labels."""

import re

from chat_analysis.keys import slugify_key

_ALIAS_SEPARATOR = re.compile(r"[（(【\[|｜@＠？?!！]")
_CJK_NAME = re.compile(r"[\u3400-\u9fff]+")
_CJK_ACTION = (
    r"(?:向|与|跟|已|将|拟|负责|需要|请|安排|确认|跟进|"
    r"提交|提醒|开通|"
    r"今晚|今天|明天|上午|中午|下午|晚上)"
)
_TITLE_TRIM = " \t\r\n@＠:：,，-—·、/|"
_LEADING_ROLE = re.compile(
    r"^(?:(?:will|is responsible for)\s+|(?:负责|将|拟|需要)(?=\S))",
    re.I,
)


def _leading_alias(text, alias):
    match = re.match(r"[@＠]?" + re.escape(alias), text, re.I)
    if not match:
        return False
    rest = text[match.end():]
    if not rest or rest[0] in _TITLE_TRIM:
        return True
    return len(alias) >= 2 and bool(
        _CJK_NAME.fullmatch(alias) and re.match(_CJK_ACTION, rest)
    )


def _matter_title(text, aliases):
    for alias in aliases:
        if _leading_alias(text, alias):
            text = _LEADING_ROLE.sub(
                "", text.lstrip("@＠")[len(alias):].lstrip(_TITLE_TRIM)
            )
            if text:
                text = text[0].upper() + text[1:]
            break
    for alias in aliases:
        if len(alias) >= 2:
            text = re.sub(
                r"(?<![^\W_])[@＠]?" + re.escape(alias) + r"(?![^\W_])",
                "", text, flags=re.I,
            )
    return re.sub(r"[ \t]{2,}", " ", text).strip(_TITLE_TRIM)


def participant_metadata(title, entity, tags, summary, senders):
    aliases = set()
    for sender in senders:
        name = str(sender or "").strip()
        if not name:
            continue
        aliases.add(name)
        short = _ALIAS_SEPARATOR.split(name, maxsplit=1)[0].strip()
        if len(short) >= 2:
            aliases.add(short)
        # A compact CJK nickname may come from the end of a display name.
        if len(short) >= 5 and _CJK_NAME.fullmatch(short):
            for size in (2, 3):
                alias = short[-size:]
                if _leading_alias(title, alias):
                    aliases.add(alias)
    aliases = sorted(aliases, key=lambda value: (-len(value), value))
    alias_keys = {slugify_key(alias, limit=None) for alias in aliases} - {""}
    key_group = "|".join(re.escape(key) for key in sorted(alias_keys))
    alias_key = re.compile(rf"(?:{key_group})(?:-(?:{key_group}))*")

    def clean_label(label):
        label = str(label or "").strip()
        if alias_key.fullmatch(slugify_key(label, limit=None)):
            return ""
        return _matter_title(label, aliases)

    entity = clean_label(entity)
    tags = [label for tag in tags if (label := clean_label(tag))][:5]
    title = _matter_title(title, aliases)
    if not title:
        first_sentence = re.split(
            r"[。！？\n]|[.!?](?:\s|$)", summary, maxsplit=1,
        )[0]
        title = _matter_title(first_sentence, aliases) or entity
    return title, entity, tags

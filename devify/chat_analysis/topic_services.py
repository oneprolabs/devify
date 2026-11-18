"""Topic and question-answer services over space-scoped analysis data."""

import json
import re
from datetime import datetime, timedelta

from django.conf import settings
from django.db.models import Exists, OuterRef, Q
from django.db.models.functions import Coalesce
from django.utils import timezone

from chat_analysis.models import (
    Event,
    EventEvidence,
    EventNote,
    Note,
    NoteEvidence,
)
from chat_domain.models import Conversation, Message
from core.tracking import LLMTracker
from spaces.services import SpacePermissionService

QUESTION_PROMPT = """You answer questions about a user's imported
conversation analysis.
Use only the supplied records. If the records do not establish an answer, say
so clearly; do not invent people, dates, decisions, or commitments.
Records were preselected from conversations or time windows named in the
question; records.scope describes that selection.
State facts only from records.events, records.notes, and records.messages.
If prior_turns is present, use them only to understand the question.
Do not copy facts from them when those facts are not in the records.
If records.related.other_conversations or records.related.outside_time
is greater than zero, add one short sentence that related material exists
outside the requested conversation or time. Do not describe it.
Write the answer in the same language as the question, using Markdown.
Start with one short sentence.
When there are several matters, make each a Markdown section:
a blank line, then a "## " heading, then "- " bullets for the details.
Put a blank line between sections.
Do not use circled numbers such as ①②③, and do not use 一、二、三 as
the only structure.
Do not use tables or code fences.
Do not repeat the citations as another list.
Return JSON with exactly: answer (string), citations (array of objects with
kind, id, title, and excerpt). Cite only supplied event, note, or message IDs.
"""

# Shortest conversation title matched against question text; one-character
# titles would match almost every question.
MIN_TITLE_MATCH_CHARS = 2
CHINESE_NUMBERS = {
    "一": 1,
    "两": 2,
    "二": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
    "十": 10,
}
RECENT_PREFIX = r"(?:近|最近|过去)"
RECENT_DAYS = re.compile(
    RECENT_PREFIX + r"\s*(\d+|[一两二三四五六七八九十])\s*(?:天|日)"
)
RECENT_WEEK = re.compile(RECENT_PREFIX + r"\s*(?:一|1)?\s*(?:个)?(?:周|星期)")
RECENT_MONTH = re.compile(RECENT_PREFIX + r"\s*(?:一|1)?\s*个?月")
THIS_WEEK = re.compile(r"本周|这周|这一周|这个星期|本星期")
LAST_WEEK = re.compile(r"上周|上星期|上一周")
THIS_MONTH = re.compile(r"本月|这个月")
LAST_MONTH = re.compile(r"上个月|上月")
TODAY = re.compile(r"今天|今日")
YESTERDAY = re.compile(r"昨天|昨日")
_CIRCLED_NUMBERS = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳"
_NUMBERED_ITEM = re.compile(r"^\d{1,2}[.、．]\s")
_CN_SECTION = re.compile(r"^[一二三四五六七八九十]、\s*(.+)$")


def format_question_answer(answer):
    """Split inline enumerations into separate lines.

    Models often write ①②③ or "1. 2. 3." inside one paragraph. The clients
    only start a new block at a line break, so those answers render as one
    lump until the markers are put on their own lines.
    """
    text = (answer or "").replace("\r\n", "\n").replace("\r", "\n")
    for index, mark in enumerate(_CIRCLED_NUMBERS, start=1):
        text = text.replace(mark, f"\n{index}. ")
    text = re.sub(r"[ \t]+(?=\d{1,2}[.、．]\s)", "\n", text)
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    formatted = []
    seen_item = False
    for line in lines:
        section = _CN_SECTION.match(line)
        if section:
            title, _, rest = section.group(1).partition(" - ")
            if formatted and formatted[-1] != "":
                formatted.append("")
            seen_item = True
            formatted.append(f"## {title.strip()}")
            details = [
                part.strip() for part in rest.split(" - ") if part.strip()
            ]
            if details:
                formatted.append("")
                formatted.extend(f"- {part}" for part in details)
            continue
        item = _NUMBERED_ITEM.match(line) is not None
        if item and formatted and not seen_item:
            formatted.append("")
        seen_item = seen_item or item
        formatted.append(line)
    return "\n".join(formatted).strip()


# Character budget for the records sent to the question model. Auto-generated
# notes are 200-message chunk summaries and can reach tens of thousands of
# characters each; without a cap one question pulled ~0.9 MB of text, the
# answer call ran past litellm's 180 s timeout, and the question failed
# (local incident, 2026-11-04).
DEFAULT_CONTEXT_CHAR_BUDGET = 60000
DEFAULT_CONTEXT_ITEM_CHARS = 800
# Notes carry most of the meaning, so they get the largest slice. Unused note
# budget rolls over to events; messages take whatever is left (15% or more).
NOTE_BUDGET_SHARE = 0.55
EVENT_BUDGET_SHARE = 0.30


def _ids(value):
    return {int(item) for item in value or []}


def _match_key(text):
    """Keep letters and digits only so emoji and spacing do not block it."""
    return "".join(char for char in (text or "").casefold() if char.isalnum())


def conversations_named_in(space, question):
    """Return ids of space conversations whose title appears in question."""
    needle = _match_key(question)
    if not needle:
        return set()
    titles = (
        Conversation.objects.filter(space=space)
        .exclude(title="")
        .values_list("id", "title")
    )
    matches = [
        (pk, _match_key(title))
        for pk, title in titles
        if len(_match_key(title)) >= MIN_TITLE_MATCH_CHARS
        and _match_key(title) in needle
    ]
    keys = [key for _, key in matches]
    return {
        pk
        for pk, key in matches
        if not any(key != other and key in other for other in keys)
    }


def question_window(question, now=None):
    """Return the closed time window named in the question, if any."""
    text = question or ""
    now = timezone.localtime(now or timezone.now())
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    days = RECENT_DAYS.search(text)
    if days:
        value = days.group(1)
        count = int(value) if value.isdigit() else CHINESE_NUMBERS[value]
        return now - timedelta(days=count), now
    if TODAY.search(text):
        return today, today + timedelta(days=1)
    if YESTERDAY.search(text):
        return today - timedelta(days=1), today
    if LAST_WEEK.search(text):
        this_week = today - timedelta(days=today.weekday())
        return this_week - timedelta(days=7), this_week
    if THIS_WEEK.search(text):
        start = today - timedelta(days=today.weekday())
        return start, start + timedelta(days=7)
    if RECENT_WEEK.search(text):
        return now - timedelta(days=7), now
    if LAST_MONTH.search(text):
        this_month = today.replace(day=1)
        previous = (this_month - timedelta(days=1)).replace(day=1)
        return previous, this_month
    if THIS_MONTH.search(text):
        start = today.replace(day=1)
        if start.month == 12:
            end = start.replace(year=start.year + 1, month=1)
        else:
            end = start.replace(month=start.month + 1)
        return start, end
    if RECENT_MONTH.search(text):
        return now - timedelta(days=30), now
    return None, None


def question_since(question, now=None):
    """Return the start of a time window named in the question, if any."""
    return question_window(question, now=now)[0]


def _context_limits():
    budget = getattr(
        settings,
        "CHAT_ANALYSIS_QUESTION_CONTEXT_CHARS",
        DEFAULT_CONTEXT_CHAR_BUDGET,
    )
    item_chars = getattr(
        settings,
        "CHAT_ANALYSIS_QUESTION_ITEM_CHARS",
        DEFAULT_CONTEXT_ITEM_CHARS,
    )
    return max(1, int(budget)), max(1, int(item_chars))


def _clip_text(text, limit):
    """Clip text to at most ``limit`` characters, marking the cut."""
    text = text or ""
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


def _fill_budget(values, budget, item_chars):
    """Clip newest-first values until the character budget is spent."""
    selected = []
    used = 0
    truncated = False
    for value in values:
        if used >= budget:
            truncated = True
            break
        text = _clip_text(value, min(item_chars, budget - used))
        if len(text) < len(value or ""):
            truncated = True
        selected.append(text)
        used += len(text)
    return selected, used, truncated


def _bound(value):
    if not value:
        return None
    if isinstance(value, str):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    else:
        parsed = value
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(
            parsed, timezone.get_current_timezone()
        )
    return parsed


def _intersect_window(left_since, left_until, right_since, right_until):
    sinces = [item for item in (left_since, right_since) if item]
    untils = [item for item in (left_until, right_until) if item]
    since = max(sinces) if sinces else None
    until = min(untils) if untils else None
    empty = bool(since and until and since >= until)
    return since, until, empty


def _conversation_boundary(events, notes, conversation_ids):
    """Keep records that stay inside the named conversations."""
    if not conversation_ids:
        return events, notes, 0
    note_in = NoteEvidence.objects.filter(
        note_id=OuterRef("pk"),
        message__conversation_id__in=conversation_ids,
    )
    note_out = NoteEvidence.objects.filter(note_id=OuterRef("pk")).exclude(
        message__conversation_id__in=conversation_ids
    )
    notes = notes.annotate(
        _note_in=Exists(note_in), _note_out=Exists(note_out)
    )
    related = notes.filter(_note_in=True, _note_out=True).count()
    notes = notes.filter(_note_in=True, _note_out=False)
    evidence_in = EventEvidence.objects.filter(
        event_id=OuterRef("pk"),
        message__conversation_id__in=conversation_ids,
    )
    evidence_out = EventEvidence.objects.filter(
        event_id=OuterRef("pk")
    ).exclude(message__conversation_id__in=conversation_ids)
    link_in = EventNote.objects.filter(
        event_id=OuterRef("pk"),
        note__evidence__message__conversation_id__in=conversation_ids,
    )
    link_out = EventNote.objects.filter(
        event_id=OuterRef("pk"),
        note__evidence__message__isnull=False,
    ).exclude(
        note__evidence__message__conversation_id__in=conversation_ids
    )
    events = events.annotate(
        _ev_in=Exists(evidence_in),
        _ev_out=Exists(evidence_out),
        _link_in=Exists(link_in),
        _link_out=Exists(link_out),
    )
    related += events.filter(
        Q(_ev_in=True) | Q(_link_in=True),
        Q(_ev_out=True) | Q(_link_out=True),
    ).count()
    events = events.filter(
        Q(_ev_in=True) | Q(_link_in=True),
        _ev_out=False,
        _link_out=False,
    )
    return events, notes, related


def _time_boundary(events, notes, since, until):
    """Keep records whose whole span sits inside the time window."""
    if not since and not until:
        return events, notes, 0
    notes = notes.annotate(
        _span_start=Coalesce("start_at", "created_at"),
        _span_end=Coalesce("end_at", "start_at", "created_at"),
    )
    overlap = notes
    inside = notes
    if since:
        overlap = overlap.filter(_span_end__gte=since)
        inside = inside.filter(_span_start__gte=since)
    if until:
        overlap = overlap.filter(_span_start__lt=until)
        inside = inside.filter(_span_end__lt=until)
    related = overlap.exclude(pk__in=inside.values("pk")).count()
    outside = Q()
    if since:
        outside |= Q(message__occurred_at__lt=since)
    if until:
        outside |= Q(message__occurred_at__gte=until)
    events = events.annotate(
        _activity=Coalesce("last_activity_at", "created_at")
    )
    if since:
        events = events.filter(_activity__gte=since)
    if until:
        events = events.filter(_activity__lt=until)
    if outside:
        spill = EventEvidence.objects.filter(
            event_id=OuterRef("pk")
        ).filter(outside)
        events = events.annotate(_spill=Exists(spill))
        related += events.filter(_spill=True).count()
        events = events.filter(_spill=False)
    return events, inside, related


def _empty_context(since, until):
    return {
        "events": [],
        "notes": [],
        "messages": [],
        "related": {"other_conversations": 0, "outside_time": 1},
        "scope": {
            "event_ids": [],
            "note_ids": [],
            "conversation_ids": [],
            "since": since.isoformat() if since else None,
            "until": until.isoformat() if until else None,
            "context_truncated": False,
        },
    }


def question_context(
    *,
    space,
    event_ids=None,
    note_ids=None,
    conversation_ids=None,
    tag_keys=None,
    keywords=None,
    since=None,
    until=None,
    empty_window=False,
):
    since = _bound(since)
    until = _bound(until)
    if empty_window:
        return _empty_context(since, until)
    event_ids = _ids(event_ids)
    note_ids = _ids(note_ids)
    conversation_ids = _ids(conversation_ids)
    events = Event.objects.filter(space=space)
    notes = Note.objects.filter(space=space)
    if note_ids:
        notes = notes.filter(id__in=note_ids)
        events = events.filter(note_links__note__in=notes).distinct()
    if event_ids:
        events = events.filter(id__in=event_ids)
        notes = notes.filter(event_links__event_id__in=event_ids).distinct()
    if tag_keys:
        events = events.filter(
            tag_assignments__tag__tag_key__in=tag_keys
        ).distinct()
    if keywords:
        event_query = Q()
        note_query = Q()
        for keyword in keywords:
            event_query |= Q(title__icontains=keyword) | Q(
                content__icontains=keyword
            )
            note_query |= Q(title__icontains=keyword) | Q(
                content__icontains=keyword
            )
        events = events.filter(event_query)
        notes = notes.filter(note_query)
    events, notes, other_conversations = _conversation_boundary(
        events, notes, conversation_ids
    )
    events, notes, outside_time = _time_boundary(events, notes, since, until)
    related = {
        "other_conversations": other_conversations,
        "outside_time": outside_time,
    }
    # Order before slicing so filtered questions also keep the newest rows.
    events = events.order_by("-last_activity_at", "-id")
    notes = notes.order_by("-start_at", "-id")
    event_rows = list(events[:101])
    note_rows = list(notes[:101])
    rows_truncated = len(event_rows) > 100 or len(note_rows) > 100
    event_rows = event_rows[:100]
    note_rows = note_rows[:100]

    budget, item_chars = _context_limits()
    note_budget = int(budget * NOTE_BUDGET_SHARE)
    note_texts, note_chars, notes_truncated = _fill_budget(
        [note.content for note in note_rows], note_budget, item_chars
    )
    selected_notes = [
        {"id": note.pk, "title": note.title, "content": text}
        for note, text in zip(note_rows, note_texts)
    ]
    event_texts, event_chars, events_truncated = _fill_budget(
        [event.content for event in event_rows],
        int(budget * EVENT_BUDGET_SHARE) + (note_budget - note_chars),
        item_chars,
    )
    selected_events = [
        {
            "id": event.pk,
            "title": event.title,
            "content": text,
            "status": event.status,
        }
        for event, text in zip(event_rows, event_texts)
    ]
    allowed_event_ids = {event["id"] for event in selected_events}
    allowed_note_ids = {note["id"] for note in selected_notes}
    messages = Message.objects.filter(
        conversation__space=space, orphaned_at__isnull=True
    )
    if conversation_ids:
        messages = messages.filter(conversation_id__in=conversation_ids)
    elif allowed_note_ids:
        messages = messages.filter(
            chat_note_evidence__note_id__in=allowed_note_ids
        ).distinct()
    if since:
        messages = messages.filter(occurred_at__gte=since)
    if until:
        messages = messages.filter(occurred_at__lt=until)
    message_rows = list(messages.order_by("-occurred_at", "-id")[:101])
    rows_truncated = rows_truncated or len(message_rows) > 100
    message_rows = message_rows[:100]
    message_texts, _, messages_truncated = _fill_budget(
        [
            " ".join(
                part
                for part in message.parts.order_by(
                    "ordinal", "id"
                ).values_list("text", flat=True)[:3]
                if part
            )
            for message in message_rows
        ],
        budget - note_chars - event_chars,
        item_chars,
    )
    selected_messages = [
        {
            "id": message.pk,
            "conversation_id": message.conversation_id,
            "sender": message.sender_name or message.sender_key,
            "occurred_at": (
                message.occurred_at.isoformat()
                if message.occurred_at
                else None
            ),
            "parts": [text] if text else [],
        }
        for message, text in zip(message_rows, message_texts)
    ]
    return {
        "events": selected_events,
        "notes": selected_notes,
        "messages": selected_messages,
        "related": related,
        "scope": {
            "event_ids": sorted(allowed_event_ids),
            "note_ids": sorted(allowed_note_ids),
            "conversation_ids": sorted(
                {message["conversation_id"] for message in selected_messages}
                | conversation_ids
            ),
            "since": since.isoformat() if since else None,
            "until": until.isoformat() if until else None,
            "context_truncated": rows_truncated
            or notes_truncated
            or events_truncated
            or messages_truncated,
        },
    }


def answer_question(
    *,
    actor,
    space,
    question,
    event_ids=None,
    note_ids=None,
    conversation_ids=None,
    tag_keys=None,
    keywords=None,
    since=None,
    until=None,
    prior_turns=None,
):
    if not SpacePermissionService.can_read(actor, space):
        raise PermissionError("Space is not visible to this user.")
    if not event_ids and not note_ids and not conversation_ids:
        conversation_ids = conversations_named_in(space, question)
    text_since, text_until = question_window(question)
    since, until, empty_window = _intersect_window(
        _bound(since), _bound(until), text_since, text_until
    )
    context = question_context(
        space=space,
        event_ids=event_ids,
        note_ids=note_ids,
        conversation_ids=conversation_ids,
        tag_keys=tag_keys,
        keywords=keywords,
        since=since,
        until=until,
        empty_window=empty_window,
    )
    payload = {"question": question, "records": context}
    if prior_turns:
        payload["prior_turns"] = prior_turns
    output, usage = LLMTracker.call_and_track(
        prompt=QUESTION_PROMPT,
        content=json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
        ),
        json_mode=True,
        max_retries=1,
        node_name="chat_question_answering",
    )
    if (
        not isinstance(output, dict)
        or not isinstance(output.get("answer"), str)
        or not output["answer"].strip()
    ):
        raise ValueError("The question model returned an empty answer.")
    citations = output.get("citations", [])
    if not isinstance(citations, list):
        citations = []
    valid = (
        {("event", item["id"]): item for item in context["events"]}
        | {("note", item["id"]): item for item in context["notes"]}
        | {("message", item["id"]): item for item in context["messages"]}
    )
    normalized_citations = []
    for item in citations:
        if not isinstance(item, dict):
            continue
        source = valid.get((item.get("kind"), item.get("id")))
        if not source:
            continue
        if item["kind"] == "message":
            title = source["sender"] or f"消息 #{source['id']}"
            excerpt = " ".join(
                part for part in source["parts"] if part
            ).strip()
            normalized_citations.append(
                {
                    "kind": item["kind"],
                    "id": source["id"],
                    "conversation_id": source["conversation_id"],
                    "title": title,
                    "excerpt": excerpt[:500],
                }
            )
        else:
            title = source["title"]
            excerpt = source["content"]
            normalized_citations.append(
                {
                    "kind": item["kind"],
                    "id": source["id"],
                    "title": title,
                    "excerpt": excerpt[:500],
                }
            )
    return {
        "question": question,
        "answer": format_question_answer(output["answer"]),
        "citations": normalized_citations,
        "scope": context["scope"],
        "usage": (
            {"model": usage.get("model")} if isinstance(usage, dict) else {}
        ),
    }

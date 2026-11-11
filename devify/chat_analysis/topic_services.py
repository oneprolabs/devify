"""Topic and question-answer services over space-scoped analysis data."""

import json
import re
from datetime import timedelta

from django.conf import settings
from django.db.models import Q
from django.utils import timezone

from chat_analysis.models import Event, Note
from chat_domain.models import Conversation, Message
from core.tracking import LLMTracker
from spaces.services import SpacePermissionService

QUESTION_PROMPT = """You answer questions about a user's imported
conversation analysis.
Use only the supplied records. If the records do not establish an answer, say
so clearly; do not invent people, dates, decisions, or commitments.
Records were preselected from conversations or time windows named in the
question; records.scope describes that selection.
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
THIS_MONTH = re.compile(r"本月|这个月")
TODAY = re.compile(r"今天|今日")
YESTERDAY = re.compile(r"昨天|昨日")


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
    return {
        pk
        for pk, title in titles
        if len(_match_key(title)) >= MIN_TITLE_MATCH_CHARS
        and _match_key(title) in needle
    }


def question_since(question, now=None):
    """Return the start of a time window named in the question, if any."""
    text = question or ""
    now = timezone.localtime(now or timezone.now())
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    days = RECENT_DAYS.search(text)
    if days:
        value = days.group(1)
        count = int(value) if value.isdigit() else CHINESE_NUMBERS[value]
        return now - timedelta(days=count)
    if TODAY.search(text):
        return today
    if YESTERDAY.search(text):
        return today - timedelta(days=1)
    if THIS_WEEK.search(text):
        return today - timedelta(days=today.weekday())
    if RECENT_WEEK.search(text):
        return now - timedelta(days=7)
    if THIS_MONTH.search(text):
        return today.replace(day=1)
    if RECENT_MONTH.search(text):
        return now - timedelta(days=30)
    return None


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


def question_context(
    *,
    space,
    event_ids=None,
    note_ids=None,
    conversation_ids=None,
    tag_keys=None,
    keywords=None,
    since=None,
):
    event_ids = _ids(event_ids)
    note_ids = _ids(note_ids)
    conversation_ids = _ids(conversation_ids)
    events = Event.objects.filter(space=space)
    notes = Note.objects.filter(space=space)
    if conversation_ids:
        notes = notes.filter(
            evidence__message__conversation_id__in=conversation_ids
        ).distinct()
        events = events.filter(note_links__note__in=notes).distinct()
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
    if since:
        events = events.filter(
            Q(last_activity_at__gte=since)
            | Q(last_activity_at__isnull=True, created_at__gte=since)
        )
        notes = notes.filter(
            Q(end_at__gte=since)
            | Q(end_at__isnull=True, start_at__gte=since)
            | Q(
                end_at__isnull=True,
                start_at__isnull=True,
                created_at__gte=since,
            )
        )
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
        "scope": {
            "event_ids": sorted(allowed_event_ids),
            "note_ids": sorted(allowed_note_ids),
            "conversation_ids": sorted(
                {message["conversation_id"] for message in selected_messages}
                | conversation_ids
            ),
            "since": since.isoformat() if since else None,
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
):
    if not SpacePermissionService.can_read(actor, space):
        raise PermissionError("Space is not visible to this user.")
    if not event_ids and not note_ids and not conversation_ids:
        conversation_ids = conversations_named_in(space, question)
    context = question_context(
        space=space,
        event_ids=event_ids,
        note_ids=note_ids,
        conversation_ids=conversation_ids,
        tag_keys=tag_keys,
        keywords=keywords,
        since=question_since(question),
    )
    output, usage = LLMTracker.call_and_track(
        prompt=QUESTION_PROMPT,
        content=json.dumps(
            {"question": question, "records": context},
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
        "answer": output["answer"].strip(),
        "citations": normalized_citations,
        "scope": context["scope"],
        "usage": (
            {"model": usage.get("model")} if isinstance(usage, dict) else {}
        ),
    }

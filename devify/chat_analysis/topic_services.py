"""Topic and question-answer services over space-scoped analysis data."""

import json

from django.conf import settings
from django.db.models import Q

from chat_analysis.models import Event, Note
from chat_domain.models import Message
from core.tracking import LLMTracker
from spaces.services import SpacePermissionService

QUESTION_PROMPT = """You answer questions about a user's imported
conversation analysis.
Use only the supplied records. If the records do not establish an answer, say
so clearly; do not invent people, dates, decisions, or commitments.
Return JSON with exactly: answer (string), citations (array of objects with
kind, id, title, and excerpt). Cite only supplied event, note, or message IDs.
"""


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
    if (
        not event_ids
        and not note_ids
        and not conversation_ids
        and not tag_keys
        and not keywords
    ):
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
    context = question_context(
        space=space,
        event_ids=event_ids,
        note_ids=note_ids,
        conversation_ids=conversation_ids,
        tag_keys=tag_keys,
        keywords=keywords,
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

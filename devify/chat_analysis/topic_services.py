"""Topic and question-answer services over space-scoped analysis data."""

import json

from django.db.models import Q

from chat_analysis.models import Event, Note
from chat_domain.models import Message
from core.tracking import LLMTracker
from spaces.services import SpacePermissionService

QUESTION_PROMPT = """You answer questions about a user's imported conversation analysis.
Use only the supplied records. If the records do not establish an answer, say so
clearly; do not invent people, dates, decisions, or commitments.
Return JSON with exactly: answer (string), citations (array of objects with kind,
id, title, and excerpt). Cite only supplied event, note, or message IDs.
"""


def _ids(value):
    return {int(item) for item in value or []}


def question_context(*, space, event_ids=None, note_ids=None, conversation_ids=None, tag_keys=None, keywords=None):
    event_ids = _ids(event_ids)
    note_ids = _ids(note_ids)
    conversation_ids = _ids(conversation_ids)
    events = Event.objects.filter(space=space)
    notes = Note.objects.filter(space=space)
    if conversation_ids:
        notes = notes.filter(evidence__message__conversation_id__in=conversation_ids).distinct()
        events = events.filter(note_links__note__in=notes).distinct()
    if note_ids:
        notes = notes.filter(id__in=note_ids)
        events = events.filter(note_links__note__in=notes).distinct()
    if event_ids:
        events = events.filter(id__in=event_ids)
        notes = notes.filter(event_links__event_id__in=event_ids).distinct()
    if tag_keys:
        events = events.filter(tag_assignments__tag__tag_key__in=tag_keys).distinct()
    if keywords:
        event_query = Q()
        note_query = Q()
        for keyword in keywords:
            event_query |= Q(title__icontains=keyword) | Q(content__icontains=keyword)
            note_query |= Q(title__icontains=keyword) | Q(content__icontains=keyword)
        events = events.filter(event_query)
        notes = notes.filter(note_query)
    if not event_ids and not note_ids and not conversation_ids and not tag_keys and not keywords:
        events = events.order_by("-last_activity_at", "-id")
        notes = notes.order_by("-start_at", "-id")
    selected_events = list(events[:100])
    selected_notes = list(notes[:100])
    allowed_event_ids = {event.pk for event in selected_events}
    allowed_note_ids = {note.pk for note in selected_notes}
    messages = Message.objects.filter(conversation__space=space)
    if conversation_ids:
        messages = messages.filter(conversation_id__in=conversation_ids)
    elif allowed_note_ids:
        messages = messages.filter(chat_note_evidence__note_id__in=allowed_note_ids).distinct()
    messages = list(messages.order_by("-occurred_at", "-id")[:100])
    return {
        "events": [{"id": e.pk, "title": e.title, "content": e.content, "status": e.status} for e in selected_events],
        "notes": [{"id": n.pk, "title": n.title, "content": n.content} for n in selected_notes],
        "messages": [{"id": m.pk, "conversation_id": m.conversation_id, "sender": m.sender_name or m.sender_key, "occurred_at": m.occurred_at.isoformat() if m.occurred_at else None, "parts": list(m.parts.order_by("ordinal", "id").values_list("text", flat=True)[:3])} for m in messages],
        "scope": {"event_ids": sorted(allowed_event_ids), "note_ids": sorted(allowed_note_ids), "conversation_ids": sorted({m.conversation_id for m in messages} | conversation_ids)},
    }


def answer_question(*, actor, space, question, event_ids=None, note_ids=None, conversation_ids=None, tag_keys=None, keywords=None):
    if not SpacePermissionService.can_read(actor, space):
        raise PermissionError("Space is not visible to this user.")
    context = question_context(space=space, event_ids=event_ids, note_ids=note_ids, conversation_ids=conversation_ids, tag_keys=tag_keys, keywords=keywords)
    output, usage = LLMTracker.call_and_track(
        prompt=QUESTION_PROMPT,
        content=json.dumps({"question": question, "records": context}, ensure_ascii=False, sort_keys=True),
        json_mode=True,
        max_retries=1,
        node_name="chat_question_answering",
    )
    if not isinstance(output, dict) or not isinstance(output.get("answer"), str) or not output["answer"].strip():
        raise ValueError("The question model returned an empty answer.")
    citations = output.get("citations", [])
    if not isinstance(citations, list):
        citations = []
    valid = {("event", item["id"]): item for item in context["events"]} | {("note", item["id"]): item for item in context["notes"]} | {("message", item["id"]): item for item in context["messages"]}
    normalized_citations = []
    for item in citations:
        if not isinstance(item, dict):
            continue
        source = valid.get((item.get("kind"), item.get("id")))
        if not source:
            continue
        if item["kind"] == "message":
            title = source["sender"] or f"消息 #{source['id']}"
            excerpt = " ".join(part for part in source["parts"] if part).strip()
            normalized_citations.append({
                "kind": item["kind"],
                "id": source["id"],
                "conversation_id": source["conversation_id"],
                "title": title,
                "excerpt": excerpt[:500],
            })
        else:
            title = source["title"]
            excerpt = source["content"]
            normalized_citations.append({"kind": item["kind"], "id": source["id"], "title": title, "excerpt": excerpt[:500]})
    return {"question": question, "answer": output["answer"].strip(), "citations": normalized_citations, "scope": context["scope"], "usage": {"model": usage.get("model")} if isinstance(usage, dict) else {}}

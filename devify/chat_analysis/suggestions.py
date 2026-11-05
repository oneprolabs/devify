from django.db import transaction
from django.utils import timezone

from chat_analysis.keys import (
    canonical_entity_key,
    canonical_event_key,
    entity_from_text,
)
from chat_analysis.models import (
    Event,
    EventEvidence,
    EventNote,
    EventSuggestion,
    EventTag,
    EventTagAssignment,
)
from chat_analysis.services import (
    ensure_can_contribute,
    refresh_event_window,
)
from chat_domain.models import Message


def _apply_tags(*, actor, event, tags):
    """Attach proposed labels to the Event, reusing space-level tags."""
    applied = []
    for label in tags or []:
        text = str(label or "").strip()
        if not text:
            continue
        tag_key = canonical_entity_key(text)
        if not tag_key:
            continue
        tag, _ = EventTag.objects.get_or_create(
            space=event.space,
            tag_key=tag_key,
            defaults={"created_by": actor, "label": text[:120]},
        )
        EventTagAssignment.objects.get_or_create(
            event=event,
            tag=tag,
            defaults={"created_by": actor},
        )
        applied.append(tag)
    return applied


@transaction.atomic
def create_event_suggestion(
    *,
    actor,
    note,
    analysis_job,
    title,
    summary,
    event_key,
    entity_key="",
    status="",
    tags=None,
    source_seqs=None,
):
    ensure_can_contribute(actor, note.space)
    canonical_key = canonical_event_key(event_key, title=title)
    if not canonical_key:
        canonical_key = canonical_event_key(
            f"{analysis_job.uuid}:{note.pk}:{title}", title=title
        )
    suggestion, _ = EventSuggestion.objects.get_or_create(
        space=note.space,
        analysis_job=analysis_job,
        note=note,
        event_key=canonical_key,
        defaults={
            "created_by": actor,
            "title": title,
            "summary": summary,
            "entity_key": canonical_entity_key(
                entity_key or entity_from_text(title, canonical_key)
            ),
            "proposed_status": status or "",
            "proposed_tags": list(tags or []),
            "source_seqs": list(source_seqs or []),
        },
    )
    return suggestion


def _resolve_source_messages(suggestion):
    """Load the messages an accepted suggestion cited, in seq order."""
    seqs = [
        int(value)
        for value in suggestion.source_seqs or []
        if str(value).isdigit()
    ]
    if not seqs:
        return []
    job = suggestion.analysis_job
    if not job.conversation_id:
        return []
    return list(
        Message.objects.filter(
            conversation_id=job.conversation_id,
            ingest_seq__in=seqs,
        ).order_by("ingest_seq")
    )


def _advance_event_status(event, status, *, source_messages):
    """Let newer evidence move an existing event's status forward."""
    if status not in Event.Status.values:
        return
    newest = max(
        (
            message.occurred_at
            for message in source_messages or []
            if message.occurred_at
        ),
        default=None,
    )
    if newest is None:
        return
    if event.last_activity_at and newest < event.last_activity_at:
        return
    if event.status != status:
        event.status = status
        event.save(update_fields=("status", "updated_at"))


@transaction.atomic
def review_event_suggestion(
    *, actor, suggestion, decision, source_messages=None
):
    ensure_can_contribute(actor, suggestion.space)
    suggestion = EventSuggestion.objects.select_for_update().get(
        pk=suggestion.pk
    )
    if suggestion.status != EventSuggestion.Status.PENDING:
        return suggestion
    suggestion.status = decision
    suggestion.reviewed_by = actor
    suggestion.reviewed_at = timezone.now()
    if decision == EventSuggestion.Status.ACCEPTED:
        if source_messages is None:
            source_messages = _resolve_source_messages(suggestion)
        canonical_key = canonical_event_key(
            suggestion.event_key, title=suggestion.title
        )
        event, created = Event.objects.get_or_create(
            space=suggestion.space,
            event_key=canonical_key,
            defaults={
                "created_by": actor,
                "title": suggestion.title,
                "content": suggestion.summary,
                "status": suggestion.proposed_status or Event.Status.OPEN,
                "entity_key": suggestion.entity_key,
            },
        )
        if not created and suggestion.proposed_status:
            _advance_event_status(
                event,
                suggestion.proposed_status,
                source_messages=source_messages,
            )
        EventNote.objects.get_or_create(
            event=event,
            note=suggestion.note,
            defaults={"created_by": actor},
        )
        _apply_tags(actor=actor, event=event, tags=suggestion.proposed_tags)
        if source_messages:
            EventEvidence.objects.bulk_create(
                [
                    EventEvidence(
                        event=event,
                        message=message,
                        created_by=actor,
                    )
                    for message in source_messages
                ],
                ignore_conflicts=True,
            )
            refresh_event_window(event, messages=source_messages)
        suggestion.event = event
    suggestion.save(
        update_fields=(
            "status",
            "reviewed_by",
            "reviewed_at",
            "event",
            "updated_at",
        )
    )
    return suggestion

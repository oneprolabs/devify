from django.db import transaction
from django.utils import timezone

from chat_analysis.models import Event, EventNote, EventSuggestion
from chat_analysis.services import ensure_can_contribute


@transaction.atomic
def create_event_suggestion(
    *, actor, note, analysis_job, title, summary, event_key
):
    ensure_can_contribute(actor, note.space)
    suggestion, _ = EventSuggestion.objects.get_or_create(
        space=note.space,
        analysis_job=analysis_job,
        note=note,
        event_key=event_key,
        defaults={
            "created_by": actor,
            "title": title,
            "summary": summary,
        },
    )
    return suggestion


@transaction.atomic
def review_event_suggestion(*, actor, suggestion, decision):
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
        event, _ = Event.objects.get_or_create(
            space=suggestion.space,
            event_key=suggestion.event_key,
            defaults={
                "created_by": actor,
                "title": suggestion.title,
                "content": suggestion.summary,
                "status": Event.Status.OPEN,
            },
        )
        EventNote.objects.get_or_create(
            event=event,
            note=suggestion.note,
            defaults={"created_by": actor},
        )
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

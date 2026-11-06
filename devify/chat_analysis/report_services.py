from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from chat_analysis.models import (
    Event,
    Note,
    Report,
    ReportItem,
    ReportItemSource,
    ReportSection,
)
from chat_analysis.services import ChatAnalysisConflict, ensure_can_contribute


def _in_period(queryset, start, end, field):
    if start:
        queryset = queryset.filter(**{f"{field}__gte": start})
    if end:
        queryset = queryset.filter(**{f"{field}__lt": end})
    return queryset


def _event_snapshot(event):
    return {
        "id": event.pk,
        "uuid": str(event.uuid),
        "title": event.title,
        "content": event.content,
        "status": event.status,
        "opened_at": event.opened_at.isoformat() if event.opened_at else None,
        "last_activity_at": (
            event.last_activity_at.isoformat()
            if event.last_activity_at
            else None
        ),
    }


def _note_snapshot(note):
    return {
        "id": note.pk,
        "uuid": str(note.uuid),
        "title": note.title,
        "content": note.content,
        "origin": note.origin,
        "start_at": note.start_at.isoformat() if note.start_at else None,
        "end_at": note.end_at.isoformat() if note.end_at else None,
    }


@transaction.atomic
def create_report_snapshot(
    *,
    actor,
    space,
    request_key,
    title,
    period_start=None,
    period_end=None,
    body_format=Report.BodyFormat.MARKDOWN,
    filters=None,
    include_open=True,
):
    ensure_can_contribute(actor, space)
    existing = Report.objects.filter(
        space=space, request_key=request_key
    ).first()
    if existing:
        if existing.title != title or (
            existing.period_start != period_start
            or existing.period_end != period_end
        ):
            raise ChatAnalysisConflict(
                "Request key conflicts with an existing report."
            )
        return existing, False

    filters = filters or {}
    events = _in_period(
        Event.objects.filter(space=space).order_by("-last_activity_at", "-id"),
        period_start,
        period_end,
        "last_activity_at",
    )
    notes = _in_period(
        Note.objects.filter(space=space).order_by("-start_at", "-id"),
        period_start,
        period_end,
        "start_at",
    )
    if filters.get("event_ids"):
        events = events.filter(pk__in=filters["event_ids"])
    if filters.get("note_ids"):
        notes = notes.filter(pk__in=filters["note_ids"])
    if filters.get("conversation_ids"):
        notes = notes.filter(evidence__message__conversation_id__in=filters["conversation_ids"]).distinct()
        events = events.filter(note_links__note__in=notes).distinct()
    if filters.get("tag_keys"):
        events = events.filter(tag_assignments__tag__tag_key__in=filters["tag_keys"]).distinct()
    if filters.get("keywords"):
        keyword_query = Q()
        for keyword in filters["keywords"]:
            keyword_query |= Q(title__icontains=keyword) | Q(content__icontains=keyword)
        events = events.filter(keyword_query)
        notes = notes.filter(keyword_query)
    if not include_open:
        events = events.filter(status=Event.Status.DONE)
    events = list(events)
    notes = list(notes)
    generated_at = timezone.now()
    report = Report.objects.create(
        space=space,
        created_by=actor,
        request_key=request_key,
        title=title,
        period_start=period_start,
        period_end=period_end,
        body_format=body_format,
        status=Report.Status.QUEUED,
        generated_at=generated_at,
        source_info={"kind": "space_snapshot"},
        processing={"generator": "rules", "version": "report.v1"},
        snapshot_ref={
            "schema_version": "report.v1",
            "generated_at": generated_at.isoformat(),
            "event_ids": [event.pk for event in events],
            "note_ids": [note.pk for note in notes],
        },
    )
    sections = [
        ("ongoing", "Ongoing events"),
        ("notes", "Notes"),
        ("done", "Completed events"),
    ]
    section_map = {
        key: ReportSection.objects.create(
            report=report,
            section_key=key,
            title=section_title,
            position=index,
        )
        for index, (key, section_title) in enumerate(sections)
    }
    body_lines = [f"# {report.title}", ""]
    if period_start or period_end:
        body_lines.extend(
            [
                f"Period: {period_start or '—'} to {period_end or '—'}",
                "",
            ]
        )

    item_count = 0
    for event in events:
        section_key = (
            "done" if event.status == Event.Status.DONE else "ongoing"
        )
        item = ReportItem.objects.create(
            section=section_map[section_key],
            position=section_map[section_key].items.count(),
            title=event.title,
            summary=event.content,
            display_kind="event",
        )
        ReportItemSource.objects.create(
            item=item,
            reference_key=f"event:{event.pk}",
            source_kind=ReportItemSource.SourceKind.EVENT,
            event=event,
            event_snapshot=_event_snapshot(event),
        )
        body_lines.extend(
            [
                f"## {event.title}",
                event.content,
                "",
            ]
        )
        item_count += 1

    for note in notes:
        item = ReportItem.objects.create(
            section=section_map["notes"],
            position=section_map["notes"].items.count(),
            title=note.title,
            summary=note.content,
            display_kind="note",
        )
        ReportItemSource.objects.create(
            item=item,
            reference_key=f"note:{note.pk}",
            source_kind=ReportItemSource.SourceKind.NOTE,
            note=note,
            note_snapshot=_note_snapshot(note),
        )
        body_lines.extend(
            [
                f"## {note.title}",
                note.content,
                "",
            ]
        )
        item_count += 1

    report.body = "\n".join(body_lines).strip()
    report.content = {
        "section_count": len(sections),
        "item_count": item_count,
        "event_count": len(events),
        "note_count": len(notes),
    }
    report.status = Report.Status.READY
    report.save(update_fields=("body", "content", "status", "updated_at"))
    return report, True

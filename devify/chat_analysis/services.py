from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from chat_analysis.keys import canonical_entity_key, canonical_event_key
from chat_analysis.models import (
    AnalysisJob,
    Event,
    EventEvidence,
    EventNote,
    EventRelation,
    Note,
    NoteEvidence,
    ReportItemSource,
)
from spaces.models import (
    SpaceWorkflowConfig,
    effective_chat_analysis_preferences,
)
from spaces.services import SpacePermissionService


class ChatAnalysisError(ValueError):
    pass


class ChatAnalysisConflict(ChatAnalysisError):
    pass


class ChatAnalysisPermissionError(PermissionError):
    pass


class ChatAnalysisPermissionService:
    """Space membership is the only access boundary for analysis results."""

    @staticmethod
    def can_view(user, space):
        return SpacePermissionService.can_read(user, space)

    @staticmethod
    def can_contribute(user, space):
        return SpacePermissionService.can_upload(user, space)

    @staticmethod
    def can_delete(user, instance):
        return SpacePermissionService.can_delete_resource(
            user, instance.space, instance.created_by_id
        )


def ensure_can_view(user, space):
    if not ChatAnalysisPermissionService.can_view(user, space):
        raise ChatAnalysisPermissionError("Space is not visible to this user.")


def ensure_can_contribute(user, space):
    if not ChatAnalysisPermissionService.can_contribute(user, space):
        raise ChatAnalysisPermissionError(
            "User cannot write analysis results in this space."
        )


def ensure_can_delete(user, instance):
    if not ChatAnalysisPermissionService.can_delete(user, instance):
        raise ChatAnalysisPermissionError(
            "User cannot delete this analysis resource."
        )


def get_analysis_preferences(space):
    config = SpaceWorkflowConfig.objects.filter(space=space).first()
    return effective_chat_analysis_preferences(
        config.chat_analysis_preferences if config else None
    )


@transaction.atomic
def create_analysis_job(
    *,
    actor,
    space,
    conversation,
    request_key,
    end_seq,
    input_version,
    start_seq=0,
    specification=None,
    analysis_preferences=None,
):
    ensure_can_contribute(actor, space)
    if conversation.space_id != space.pk:
        raise ChatAnalysisError("Conversation must belong to the same space.")
    preferences = (
        effective_chat_analysis_preferences(analysis_preferences)
        if analysis_preferences is not None
        else get_analysis_preferences(space)
    )
    cutoff_days = preferences.get("lookback_days", 0)
    snapshot = dict(specification or {})
    snapshot["analysis_conversation_kind"] = conversation.kind
    snapshot["chat_analysis_preferences"] = preferences
    snapshot["analysis_cutoff"] = (
        (timezone.now() - timedelta(days=cutoff_days)).isoformat()
        if cutoff_days else None
    )
    job, created = AnalysisJob.objects.get_or_create(
        space=space,
        request_key=request_key,
        defaults={
            "created_by": actor,
            "conversation": conversation,
            "start_seq": start_seq,
            "end_seq": end_seq,
            "input_version": input_version,
            "specification": snapshot,
        },
    )
    if not created and (
        job.conversation_id != conversation.pk
        or job.start_seq != start_seq
        or job.end_seq != end_seq
        or job.input_version != input_version
    ):
        raise ChatAnalysisConflict(
            "Request key conflicts with an existing analysis job."
        )
    return job


@transaction.atomic
def retry_analysis_job(*, actor, job):
    """Requeue a terminal analysis job after checking current permissions."""
    ensure_can_contribute(actor, job.space)
    job = AnalysisJob.objects.select_for_update().get(pk=job.pk)
    if job.state not in (
        AnalysisJob.State.FAILED,
        AnalysisJob.State.PARTIAL,
    ):
        raise ChatAnalysisConflict(
            "Only failed or partial analysis jobs can be retried."
        )
    job.state = AnalysisJob.State.QUEUED
    job.lease_owner = ""
    job.lease_until = None
    job.error = ""
    job.save(
        update_fields=(
            "state",
            "lease_owner",
            "lease_until",
            "error",
            "updated_at",
        )
    )
    return job


@transaction.atomic
def cancel_analysis_job(*, actor, job):
    ensure_can_contribute(actor, job.space)
    locked = AnalysisJob.objects.select_for_update().get(pk=job.pk)
    if locked.state in (
        AnalysisJob.State.READY,
        AnalysisJob.State.PARTIAL,
        AnalysisJob.State.FAILED,
        AnalysisJob.State.CANCELLED,
    ):
        raise ChatAnalysisConflict(
            "Only queued or running analysis jobs can be cancelled."
        )
    locked.state = AnalysisJob.State.CANCELLED
    locked.lease_owner = ""
    locked.lease_until = None
    locked.error = "Cancelled by user."
    locked.save(
        update_fields=(
            "state",
            "lease_owner",
            "lease_until",
            "error",
            "updated_at",
        )
    )
    return locked


@transaction.atomic
def create_note(
    *,
    actor,
    space,
    note_key,
    title,
    content,
    origin=Note.Origin.AUTO,
    start_at=None,
    end_at=None,
    analysis_job=None,
):
    ensure_can_contribute(actor, space)
    note = Note.objects.filter(space=space, note_key=note_key).first()
    if (
        note
        and note.origin == Note.Origin.MANUAL
        and origin != Note.Origin.MANUAL
    ):
        return note
    if note:
        note.title = title
        note.content = content
        note.start_at = start_at
        note.end_at = end_at
        note.origin = origin
        note.analysis_job = analysis_job or note.analysis_job
        note.save()
        return note
    return Note.objects.create(
        space=space,
        created_by=actor,
        analysis_job=analysis_job,
        note_key=note_key,
        title=title,
        content=content,
        start_at=start_at,
        end_at=end_at,
        origin=origin,
    )


@transaction.atomic
def add_note_evidence(*, actor, note, message, message_part=None):
    ensure_can_contribute(actor, note.space)
    reference_key = NoteEvidence.build_reference_key(
        message.pk, message_part.pk if message_part else None
    )
    evidence, _ = NoteEvidence.objects.get_or_create(
        note=note,
        reference_key=reference_key,
        defaults={
            "message": message,
            "message_part": message_part,
        },
    )
    return evidence


@transaction.atomic
def create_event(
    *,
    actor,
    space,
    event_key,
    title,
    content,
    status=None,
    opened_at=None,
    last_activity_at=None,
    entity_key="",
):
    ensure_can_contribute(actor, space)
    event, _ = Event.objects.get_or_create(
        space=space,
        event_key=canonical_event_key(event_key, title=title),
        defaults={
            "created_by": actor,
            "title": title,
            "content": content,
            "status": status,
            "opened_at": opened_at,
            "last_activity_at": last_activity_at,
            "entity_key": canonical_entity_key(entity_key),
        },
    )
    return event


def refresh_event_window(event, *, messages=None):
    """Recompute an Event's activity window from its own evidence.

    Only widens the window: an event keeps its earliest start and latest
    activity even when older evidence is later attached.
    """
    if messages is None:
        occurred = list(
            EventEvidence.objects.filter(event=event).values_list(
                "message__occurred_at", flat=True
            )
        )
    else:
        occurred = [message.occurred_at for message in messages]
    occurred = [value for value in occurred if value]
    if not occurred:
        return event
    opened_at = min(occurred)
    last_activity_at = max(occurred)
    changed = []
    if event.opened_at is None or opened_at < event.opened_at:
        event.opened_at = opened_at
        changed.append("opened_at")
    if (
        event.last_activity_at is None
        or last_activity_at > event.last_activity_at
    ):
        event.last_activity_at = last_activity_at
        changed.append("last_activity_at")
    if changed:
        event.save(update_fields=tuple(changed) + ("updated_at",))
    return event


@transaction.atomic
def merge_events(*, actor, source, target):
    """Fold one Event into another and drop the source row."""
    ensure_can_contribute(actor, source.space)
    if source.space_id != target.space_id:
        raise ChatAnalysisError("Events must share a space.")
    if source.pk == target.pk:
        return target
    for link in EventNote.objects.filter(event=source).select_related("note"):
        EventNote.objects.get_or_create(
            event=target,
            note=link.note,
            defaults={"created_by": link.created_by},
        )
    for link in EventEvidence.objects.filter(event=source).select_related(
        "message"
    ):
        EventEvidence.objects.get_or_create(
            event=target,
            message=link.message,
            defaults={"created_by": link.created_by},
        )
    ReportItemSource.objects.filter(event=source).update(event=target)
    refresh_event_window(target)
    source.delete()
    return target


@transaction.atomic
def assign_note_events(*, actor, note, events, manual=True):
    """Replace the Note's full event set.

    Automatic association never changes a Note whose assignment was confirmed
    by a human, including the explicit "no event" decision.
    """
    ensure_can_contribute(actor, note.space)
    note = Note.objects.select_for_update().get(pk=note.pk)
    events = list(events)
    if any(event.space_id != note.space_id for event in events):
        raise ChatAnalysisError("Note and events must share a space.")
    if not manual and note.assignment_mode == Note.AssignmentMode.MANUAL:
        return False
    EventNote.objects.filter(note=note).delete()
    EventNote.objects.bulk_create(
        [
            EventNote(event=event, note=note, created_by=actor)
            for event in events
        ]
    )
    if manual:
        note.assignment_mode = Note.AssignmentMode.MANUAL
        note.save(update_fields=("assignment_mode", "updated_at"))
    return True


@transaction.atomic
def upsert_event_relation(
    *,
    actor,
    space,
    left_event,
    right_event,
    relation_kind,
    decision=EventRelation.Decision.PENDING,
    reason="",
    source_note_ids=None,
):
    ensure_can_contribute(actor, space)
    if {left_event.space_id, right_event.space_id} != {space.pk}:
        raise ChatAnalysisError("Related events must share a space.")
    if left_event.pk == right_event.pk:
        raise ChatAnalysisError("An event cannot be related to itself.")
    left_id, right_id = sorted((left_event.pk, right_event.pk))
    decided = decision != EventRelation.Decision.PENDING
    values = {
        "relation_kind": relation_kind,
        "decision": decision,
        "reason": reason,
        "source_note_ids": source_note_ids or [],
        "decided_by": actor if decided else None,
        "decided_at": timezone.now() if decided else None,
    }
    relation, created = EventRelation.objects.get_or_create(
        space=space,
        left_event_id=left_id,
        right_event_id=right_id,
        defaults={"created_by": actor, **values},
    )
    if not created:
        for field, value in values.items():
            setattr(relation, field, value)
        relation.save()
    return relation


def delete_note(*, actor, note):
    ensure_can_delete(actor, note)
    note.delete()


def delete_event(*, actor, event):
    ensure_can_delete(actor, event)
    event.delete()

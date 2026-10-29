from django.db import transaction
from django.utils import timezone

from chat_analysis.models import (
    AnalysisJob,
    Event,
    EventNote,
    EventRelation,
    Note,
    NoteEvidence,
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
):
    ensure_can_contribute(actor, space)
    if conversation.space_id != space.pk:
        raise ChatAnalysisError("Conversation must belong to the same space.")
    job, created = AnalysisJob.objects.get_or_create(
        space=space,
        request_key=request_key,
        defaults={
            "created_by": actor,
            "conversation": conversation,
            "start_seq": start_seq,
            "end_seq": end_seq,
            "input_version": input_version,
            "specification": specification or {},
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
):
    ensure_can_contribute(actor, space)
    event, _ = Event.objects.get_or_create(
        space=space,
        event_key=event_key,
        defaults={
            "created_by": actor,
            "title": title,
            "content": content,
            "status": status,
            "opened_at": opened_at,
            "last_activity_at": last_activity_at,
        },
    )
    return event


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

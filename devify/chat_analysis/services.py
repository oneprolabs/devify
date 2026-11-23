from datetime import timedelta

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from chat_analysis.keys import canonical_entity_key, canonical_event_key
from chat_analysis.models import (
    AnalysisJob,
    Event,
    EventEvidence,
    EventNote,
    EventRelation,
    EventSuggestion,
    EventTagAssignment,
    Note,
    NoteEvidence,
    QuestionAnswer,
    ReportItemSource,
)
from chat_analysis.user_dispatch import lock_dispatch_row
from chat_domain.models import MessagePart
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


def readable_text_parts(message_id):
    """Use the same non-whitespace text requirement as message extraction."""
    return MessagePart.objects.filter(
        message_id=message_id,
        kind=MessagePart.Kind.TEXT,
        text__regex=r"(*UCP)[^\s\x1c-\x1f]",
    )


def disallowed_conversation_q(kind_field, preferences_field):
    types = f"{preferences_field}__conversation_types__contains"
    return Q(**{f"{preferences_field}__has_key": "conversation_types"}) & (
        (Q(**{kind_field: "direct"}) & ~Q(**{types: ["direct"]}))
        | (Q(**{kind_field: "group"}) & ~Q(**{types: ["group"]}))
        | (Q(**{kind_field: "unknown"}) & ~Q(**{types: ["direct", "group"]}))
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
    lock_dispatch_row()
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
        if cutoff_days
        else None
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
        job.created_by_id != actor.pk
        or job.conversation_id != conversation.pk
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
    lock_dispatch_row()
    job = AnalysisJob.objects.select_for_update().get(pk=job.pk)
    if job.state not in (
        AnalysisJob.State.FAILED,
        AnalysisJob.State.PARTIAL,
    ):
        raise ChatAnalysisConflict(
            "Only failed or partial analysis jobs can be retried."
        )
    job.state = AnalysisJob.State.QUEUED
    job.checkpoint = dict(job.checkpoint)
    job.checkpoint.pop("resume_after", None)
    job.checkpoint.pop("publication_failures", None)
    job.lease_owner = ""
    job.lease_until = None
    job.error = ""
    job.save(
        update_fields=(
            "state",
            "checkpoint",
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
    lock_dispatch_row()
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
    now = timezone.now()
    event, _ = Event.objects.get_or_create(
        space=space,
        event_key=canonical_event_key(event_key, title=title),
        defaults={
            "created_by": actor,
            "title": title,
            "content": content,
            "status": status,
            # Manual events have no evidence window yet. Giving them the
            # creation time keeps them visible in the event list and inside
            # report periods instead of being filtered out by a NULL time.
            "opened_at": opened_at or now,
            "last_activity_at": last_activity_at or now,
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


def merge_blocked_by_relation(relation):
    return (
        relation.decision == EventRelation.Decision.ACCEPTED
        and relation.relation_kind != EventRelation.RelationKind.SAME
    ) or (
        relation.decision == EventRelation.Decision.REJECTED
        and relation.relation_kind == EventRelation.RelationKind.SAME
    )


def _move_event_relations(source, target):
    relations = EventRelation.objects.select_for_update().filter(
        Q(left_event=source) | Q(right_event=source)
    )
    pending = EventRelation.Decision.PENDING
    for relation in relations:
        other_id = relation.right_event_id
        if relation.right_event_id == source.pk:
            other_id = relation.left_event_id
        if other_id == target.pk:
            if merge_blocked_by_relation(relation):
                raise ChatAnalysisConflict(
                    f"Event relation #{relation.pk} blocks this merge."
                )
            continue
        left_id, right_id = sorted((target.pk, other_id))
        existing = (
            EventRelation.objects.select_for_update()
            .filter(
                space_id=target.space_id,
                left_event_id=left_id,
                right_event_id=right_id,
            )
            .first()
        )
        if existing is None:
            relation.left_event_id = left_id
            relation.right_event_id = right_id
            relation.save(
                update_fields=("left_event", "right_event", "updated_at")
            )
            continue
        if (
            relation.decision != pending
            and existing.decision != pending
            and (relation.relation_kind, relation.decision)
            != (existing.relation_kind, existing.decision)
        ):
            raise ChatAnalysisConflict(
                f"Event relations #{relation.pk} and #{existing.pk} conflict."
            )
        if existing.decision == pending and relation.decision != pending:
            existing.relation_kind = relation.relation_kind
            existing.decision = relation.decision
            existing.decided_by_id = relation.decided_by_id
            existing.decided_at = relation.decided_at
        existing.source_note_ids = list(
            dict.fromkeys(existing.source_note_ids + relation.source_note_ids)
        )
        existing.reason = "\n".join(
            dict.fromkeys(
                reason
                for reason in (existing.reason, relation.reason)
                if reason
            )
        )
        existing.save()


def _move_event_citations(source, target):
    questions = QuestionAnswer.objects.select_for_update().filter(
        space_id=source.space_id
    )
    for question in questions.iterator():
        changed_fields = []
        for citation in question.citations:
            if (
                isinstance(citation, dict)
                and citation.get("kind") == "event"
                and citation.get("id") == source.pk
            ):
                citation["id"] = target.pk
                changed_fields = ["citations"]
        event_ids = question.scope.get("event_ids", [])
        if source.pk in event_ids:
            question.scope["event_ids"] = list(
                dict.fromkeys(
                    target.pk if event_id == source.pk else event_id
                    for event_id in event_ids
                )
            )
            changed_fields.append("scope")
        if changed_fields:
            question.save(update_fields=changed_fields + ["updated_at"])


@transaction.atomic
def merge_events(*, actor, source, target):
    """Fold an event into another and preserve its links."""
    ensure_can_contribute(actor, source.space)
    if source.space_id != target.space_id:
        raise ChatAnalysisError("Events must share a space.")
    if source.pk == target.pk:
        return target
    locked = {
        event.pk: event
        for event in Event.objects.select_for_update()
        .filter(pk__in=(source.pk, target.pk))
        .order_by("pk")
    }
    if source.pk not in locked or target.pk not in locked:
        raise ChatAnalysisConflict("An event was already removed.")
    source, target = locked[source.pk], locked[target.pk]
    _move_event_relations(source, target)
    for model, field in (
        (EventNote, "note_id"),
        (EventEvidence, "message_id"),
        (EventTagAssignment, "tag_id"),
    ):
        retained = list(
            model.objects.filter(event=target).values_list(field, flat=True)
        )
        model.objects.filter(event=source).exclude(
            **{f"{field}__in": retained}
        ).update(event=target)
    EventSuggestion.objects.filter(event=source).update(event=target)
    ReportItemSource.objects.filter(event=source).update(event=target)
    _move_event_citations(source, target)
    changed = []
    if source.opened_at and (
        not target.opened_at or source.opened_at < target.opened_at
    ):
        target.opened_at = source.opened_at
        changed.append("opened_at")
    if source.last_activity_at and (
        not target.last_activity_at
        or source.last_activity_at > target.last_activity_at
    ):
        target.last_activity_at = source.last_activity_at
        changed.append("last_activity_at")
    if changed:
        target.save(update_fields=changed + ["updated_at"])
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

import pytest
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from chat_analysis.models import (
    AnalysisJob,
    Event,
    EventNote,
    EventRelation,
    Note,
    NoteEvidence,
)
from chat_domain.models import Conversation, Message, MessagePart
from spaces.models import Space, SpaceMembership

pytestmark = [pytest.mark.django_db, pytest.mark.integration]


def make_space(owner, slug="analysis-team", kind=Space.Kind.TEAM):
    space = Space.objects.create(
        name=slug,
        slug=slug,
        kind=kind,
        owner=owner,
    )
    SpaceMembership.objects.create(
        space=space,
        user=owner,
        role=SpaceMembership.Role.OWNER,
    )
    return space


def make_conversation(space, key="group-a"):
    return Conversation.objects.create(
        space=space,
        platform=Conversation.Platform.WECHAT,
        source_namespace="local-account",
        source_conversation_id=key,
        identity_key=f"wechat:local-account:{key}",
        title=key,
    )


def make_message(space, key="group-a"):
    conversation = make_conversation(space, key=key)
    return Message.objects.create(
        conversation=conversation,
        message_key=f"{key}-m-1",
        ingest_seq=1,
    )


def make_note(space, author, key="note-1"):
    return Note.objects.create(
        space=space,
        created_by=author,
        note_key=key,
        title="Pricing follow-up",
        content="Customer asked for the annual quote.",
    )


def make_event(space, author, key="event-1"):
    return Event.objects.create(
        space=space,
        created_by=author,
        event_key=key,
        title="Annual quote",
        content="Customer is waiting for the annual quote.",
    )


def test_evidence_must_come_from_the_same_space_as_the_note():
    owner = User.objects.create_user(username="evidence-owner")
    space = make_space(owner)
    other_space = make_space(owner, slug="other-team")
    foreign_message = make_message(other_space, key="other-group")
    note = make_note(space, owner)

    with pytest.raises(ValidationError):
        NoteEvidence.objects.create(
            note=note,
            message=foreign_message,
        )

    message = make_message(space)
    evidence = NoteEvidence.objects.create(note=note, message=message)
    assert evidence.reference_key == f"{message.pk}:whole"


def test_evidence_reference_key_is_unique_per_note():
    owner = User.objects.create_user(username="evidence-unique-owner")
    space = make_space(owner)
    message = make_message(space)
    note = make_note(space, owner)

    NoteEvidence.objects.create(note=note, message=message)
    with pytest.raises(IntegrityError), transaction.atomic():
        NoteEvidence.objects.create(note=note, message=message)

    part = MessagePart.objects.create(
        message=message,
        part_key="p-1",
        kind=MessagePart.Kind.TEXT,
    )
    part_evidence = NoteEvidence.objects.create(
        note=note, message=message, message_part=part
    )
    assert part_evidence.reference_key == f"{message.pk}:{part.pk}"


def test_evidence_part_must_belong_to_the_message():
    owner = User.objects.create_user(username="evidence-part-owner")
    space = make_space(owner)
    message = make_message(space)
    other_message = make_message(space, key="group-b")
    note = make_note(space, owner)
    foreign_part = MessagePart.objects.create(
        message=other_message,
        part_key="p-1",
        kind=MessagePart.Kind.TEXT,
    )

    with pytest.raises(ValidationError):
        NoteEvidence.objects.create(
            note=note,
            message=message,
            message_part=foreign_part,
        )


def test_event_note_rejects_notes_from_another_space():
    owner = User.objects.create_user(username="event-note-owner")
    space = make_space(owner)
    other_space = make_space(owner, slug="event-note-other")
    note = make_note(other_space, owner)
    event = make_event(space, owner)

    with pytest.raises(ValidationError):
        EventNote.objects.create(event=event, note=note, created_by=owner)

    same_space_note = make_note(space, owner)
    link = EventNote.objects.create(
        event=event, note=same_space_note, created_by=owner
    )
    assert link.event_id == event.pk


def test_event_relation_is_stored_in_canonical_order():
    owner = User.objects.create_user(username="relation-owner")
    space = make_space(owner)
    first = make_event(space, owner, key="event-a")
    second = make_event(space, owner, key="event-b")
    left, right = sorted((first, second), key=lambda event: event.pk)

    relation = EventRelation.objects.create(
        space=space,
        left_event=right,
        right_event=left,
        relation_kind=EventRelation.RelationKind.RELATED,
        created_by=owner,
    )

    assert relation.left_event_id == left.pk
    assert relation.right_event_id == right.pk
    with pytest.raises(IntegrityError), transaction.atomic():
        EventRelation.objects.create(
            space=space,
            left_event=left,
            right_event=right,
            relation_kind=EventRelation.RelationKind.SEPARATE,
            created_by=owner,
        )


def test_event_relation_rejects_cross_space_or_self_relations():
    owner = User.objects.create_user(username="relation-guard-owner")
    space = make_space(owner)
    other_space = make_space(owner, slug="relation-guard-other")
    event = make_event(space, owner)
    other_event = make_event(other_space, owner, key="event-other")

    with pytest.raises(ValidationError):
        EventRelation.objects.create(
            space=space,
            left_event=event,
            right_event=other_event,
            relation_kind=EventRelation.RelationKind.SAME,
            created_by=owner,
        )

    with pytest.raises(ValidationError):
        EventRelation.objects.create(
            space=space,
            left_event=event,
            right_event=event,
            relation_kind=EventRelation.RelationKind.SAME,
            created_by=owner,
        )


def test_analysis_job_validates_window_and_conversation_space():
    owner = User.objects.create_user(username="job-owner")
    space = make_space(owner)
    other_space = make_space(owner, slug="job-other")
    conversation = make_conversation(space)
    foreign_conversation = make_conversation(other_space, key="job-other")

    with pytest.raises(ValidationError):
        AnalysisJob.objects.create(
            space=space,
            created_by=owner,
            conversation=conversation,
            request_key="job-1",
            start_seq=10,
            end_seq=5,
            input_version="wechat.v1",
        )

    with pytest.raises(ValidationError):
        AnalysisJob.objects.create(
            space=space,
            created_by=owner,
            conversation=foreign_conversation,
            request_key="job-2",
            start_seq=0,
            end_seq=5,
            input_version="wechat.v1",
        )

    job = AnalysisJob.objects.create(
        space=space,
        created_by=owner,
        conversation=conversation,
        request_key="job-3",
        start_seq=0,
        end_seq=5,
        input_version="wechat.v1",
    )
    assert job.state == AnalysisJob.State.QUEUED
    assert job.fencing_token == 0


def test_note_business_time_requires_a_valid_range():
    owner = User.objects.create_user(username="note-time-owner")
    space = make_space(owner)

    with pytest.raises(ValidationError):
        Note.objects.create(
            space=space,
            created_by=owner,
            note_key="note-end-only",
            title="Invalid",
            content="Missing start",
            end_at="2026-10-01T00:00:00Z",
        )

    with pytest.raises(ValidationError):
        Note.objects.create(
            space=space,
            created_by=owner,
            note_key="note-reversed",
            title="Invalid",
            content="End before start",
            start_at="2026-10-02T00:00:00Z",
            end_at="2026-10-01T00:00:00Z",
        )

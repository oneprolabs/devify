import pytest
from django.contrib.auth.models import User

from chat_analysis.models import Event, EventNote, EventRelation, Note
from chat_analysis.services import (
    ChatAnalysisConflict,
    add_note_evidence,
    assign_note_events,
    create_analysis_job,
    create_event,
    create_note,
    upsert_event_relation,
)
from chat_domain.models import Conversation, Message
from spaces.models import Space, SpaceMembership

pytestmark = [pytest.mark.django_db, pytest.mark.integration]


def make_space(owner, slug="service-team"):
    space = Space.objects.create(
        name=slug,
        slug=slug,
        kind=Space.Kind.TEAM,
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


def test_analysis_job_creation_is_idempotent_per_request_key():
    owner = User.objects.create_user(username="service-job-owner")
    space = make_space(owner)
    conversation = make_conversation(space)

    first = create_analysis_job(
        actor=owner,
        space=space,
        conversation=conversation,
        request_key="job-1",
        end_seq=10,
        input_version="wechat.v1",
    )
    second = create_analysis_job(
        actor=owner,
        space=space,
        conversation=conversation,
        request_key="job-1",
        end_seq=10,
        input_version="wechat.v1",
    )

    assert first.pk == second.pk
    with pytest.raises(ChatAnalysisConflict):
        create_analysis_job(
            actor=owner,
            space=space,
            conversation=conversation,
            request_key="job-1",
            end_seq=20,
            input_version="wechat.v1",
        )


def test_auto_rerun_does_not_overwrite_a_manual_note():
    owner = User.objects.create_user(username="service-note-owner")
    space = make_space(owner)

    manual = create_note(
        actor=owner,
        space=space,
        note_key="note-1",
        title="Manual title",
        content="Confirmed by a human.",
        origin=Note.Origin.MANUAL,
    )
    rerun = create_note(
        actor=owner,
        space=space,
        note_key="note-1",
        title="Automated title",
        content="Automated content.",
        origin=Note.Origin.AUTO,
    )

    assert rerun.pk == manual.pk
    rerun.refresh_from_db()
    assert rerun.title == "Manual title"
    assert rerun.origin == Note.Origin.MANUAL


def test_auto_rerun_refreshes_an_automatic_note():
    owner = User.objects.create_user(username="service-auto-owner")
    space = make_space(owner)

    create_note(
        actor=owner,
        space=space,
        note_key="note-1",
        title="First title",
        content="First content.",
    )
    rerun = create_note(
        actor=owner,
        space=space,
        note_key="note-1",
        title="Second title",
        content="Second content.",
    )

    assert Note.objects.filter(space=space).count() == 1
    assert rerun.title == "Second title"


def test_adding_the_same_evidence_twice_does_not_duplicate_it():
    owner = User.objects.create_user(username="service-evidence-owner")
    space = make_space(owner)
    message = make_message(space)
    note = create_note(
        actor=owner,
        space=space,
        note_key="note-1",
        title="Note",
        content="Content.",
    )

    first = add_note_evidence(actor=owner, note=note, message=message)
    second = add_note_evidence(actor=owner, note=note, message=message)

    assert first.pk == second.pk
    assert note.evidence.count() == 1


def test_manual_assignment_is_never_changed_by_automatic_association():
    owner = User.objects.create_user(username="service-assign-owner")
    space = make_space(owner)
    note = create_note(
        actor=owner,
        space=space,
        note_key="note-1",
        title="Note",
        content="Content.",
    )
    event = create_event(
        actor=owner,
        space=space,
        event_key="event-1",
        title="Event",
        content="Content.",
    )
    other_event = create_event(
        actor=owner,
        space=space,
        event_key="event-2",
        title="Other event",
        content="Content.",
    )

    assert assign_note_events(
        actor=owner, note=note, events=[event], manual=True
    )
    note.refresh_from_db()
    assert note.assignment_mode == Note.AssignmentMode.MANUAL

    assert not assign_note_events(
        actor=owner, note=note, events=[other_event], manual=False
    )
    assert list(
        EventNote.objects.filter(note=note).values_list("event_id", flat=True)
    ) == [event.pk]

    assert assign_note_events(actor=owner, note=note, events=[], manual=True)
    assert not EventNote.objects.filter(note=note).exists()
    note.refresh_from_db()
    assert note.assignment_mode == Note.AssignmentMode.MANUAL


def test_automatic_association_can_move_an_automatic_note():
    owner = User.objects.create_user(username="service-auto-assign-owner")
    space = make_space(owner)
    note = create_note(
        actor=owner,
        space=space,
        note_key="note-1",
        title="Note",
        content="Content.",
    )
    event = create_event(
        actor=owner,
        space=space,
        event_key="event-1",
        title="Event",
        content="Content.",
    )

    assert assign_note_events(
        actor=owner, note=note, events=[event], manual=False
    )
    note.refresh_from_db()
    assert note.assignment_mode == Note.AssignmentMode.AUTO


def test_event_relation_upsert_reuses_canonical_pair():
    owner = User.objects.create_user(username="service-relation-owner")
    maintainer = User.objects.create_user(username="service-relation-maint")
    space = make_space(owner)
    SpaceMembership.objects.create(
        space=space,
        user=maintainer,
        role=SpaceMembership.Role.MAINTAINER,
    )
    first = create_event(
        actor=owner, space=space, event_key="event-a", title="A", content="A."
    )
    second = create_event(
        actor=owner, space=space, event_key="event-b", title="B", content="B."
    )

    relation = upsert_event_relation(
        actor=owner,
        space=space,
        left_event=second,
        right_event=first,
        relation_kind=EventRelation.RelationKind.RELATED,
    )
    assert relation.decision == EventRelation.Decision.PENDING
    assert relation.decided_at is None

    accepted = upsert_event_relation(
        actor=maintainer,
        space=space,
        left_event=first,
        right_event=second,
        relation_kind=EventRelation.RelationKind.SAME,
        decision=EventRelation.Decision.ACCEPTED,
        reason="Same request.",
    )

    assert accepted.pk == relation.pk
    assert Event.objects.filter(space=space).count() == 2
    assert accepted.decision == EventRelation.Decision.ACCEPTED
    assert accepted.created_by_id == owner.pk
    assert accepted.decided_by_id == maintainer.pk
    assert accepted.decided_at is not None

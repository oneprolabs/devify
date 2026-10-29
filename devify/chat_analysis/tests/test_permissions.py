import pytest
from django.contrib.auth.models import User

from chat_analysis.models import Event, Note
from chat_analysis.services import (
    ChatAnalysisPermissionError,
    ChatAnalysisPermissionService,
    assign_note_events,
    create_analysis_job,
    create_event,
    create_note,
    delete_event,
    delete_note,
)
from chat_domain.models import Conversation
from spaces.models import Space, SpaceMembership, SpaceTakeover

pytestmark = [pytest.mark.django_db, pytest.mark.integration]


def make_team(owner, slug="permission-team", status=Space.Status.ACTIVE):
    space = Space.objects.create(
        name=slug,
        slug=slug,
        kind=Space.Kind.TEAM,
        owner=owner,
        status=status,
    )
    SpaceMembership.objects.create(
        space=space,
        user=owner,
        role=SpaceMembership.Role.OWNER,
    )
    return space


def add_member(space, user, role):
    return SpaceMembership.objects.create(space=space, user=user, role=role)


def make_conversation(space, key="permission-group"):
    return Conversation.objects.create(
        space=space,
        platform=Conversation.Platform.WECHAT,
        source_namespace="local-account",
        source_conversation_id=key,
        identity_key=f"wechat:local-account:{key}",
        title=key,
    )


def test_guest_can_read_but_cannot_create_analysis_results():
    owner = User.objects.create_user(username="permission-guest-owner")
    guest = User.objects.create_user(username="permission-guest")
    space = make_team(owner)
    add_member(space, guest, SpaceMembership.Role.GUEST)
    conversation = make_conversation(space)

    assert ChatAnalysisPermissionService.can_view(guest, space)
    with pytest.raises(ChatAnalysisPermissionError):
        create_note(
            actor=guest,
            space=space,
            note_key="guest-note",
            title="Guest",
            content="Guest.",
        )
    with pytest.raises(ChatAnalysisPermissionError):
        create_event(
            actor=guest,
            space=space,
            event_key="guest-event",
            title="Guest",
            content="Guest.",
        )
    with pytest.raises(ChatAnalysisPermissionError):
        create_analysis_job(
            actor=guest,
            space=space,
            conversation=conversation,
            request_key="guest-job",
            end_seq=1,
            input_version="wechat.v1",
        )


def test_non_members_and_removed_members_have_no_access():
    owner = User.objects.create_user(username="permission-owner")
    outsider = User.objects.create_user(username="permission-outsider")
    removed = User.objects.create_user(username="permission-removed")
    space = make_team(owner)
    membership = add_member(space, removed, SpaceMembership.Role.USER)
    membership.status = SpaceMembership.Status.REMOVED
    membership.save(update_fields=("status",))

    assert not ChatAnalysisPermissionService.can_view(outsider, space)
    assert not ChatAnalysisPermissionService.can_view(removed, space)
    with pytest.raises(ChatAnalysisPermissionError):
        create_note(
            actor=removed,
            space=space,
            note_key="removed-note",
            title="Removed",
            content="Removed.",
        )


def test_archived_space_blocks_writes_but_keeps_reads():
    owner = User.objects.create_user(username="permission-archived-owner")
    space = make_team(owner, status=Space.Status.ARCHIVED)

    assert ChatAnalysisPermissionService.can_view(owner, space)
    with pytest.raises(ChatAnalysisPermissionError):
        create_note(
            actor=owner,
            space=space,
            note_key="archived-note",
            title="Archived",
            content="Archived.",
        )


def test_global_admin_needs_an_active_takeover():
    owner = User.objects.create_user(username="permission-admin-owner")
    admin = User.objects.create_user(
        username="permission-admin", is_staff=True
    )
    space = make_team(owner)
    conversation = make_conversation(space)

    assert not ChatAnalysisPermissionService.can_view(admin, space)
    with pytest.raises(ChatAnalysisPermissionError):
        create_note(
            actor=admin,
            space=space,
            note_key="admin-note",
            title="Admin",
            content="Admin.",
        )

    SpaceTakeover.objects.create(space=space, admin=admin, reason="audit")
    assert ChatAnalysisPermissionService.can_view(admin, space)
    note = create_note(
        actor=admin,
        space=space,
        note_key="admin-note",
        title="Admin",
        content="Admin.",
    )
    assert note.created_by_id == admin.pk
    create_analysis_job(
        actor=admin,
        space=space,
        conversation=conversation,
        request_key="admin-job",
        end_seq=1,
        input_version="wechat.v1",
    )


def test_only_the_author_or_a_space_admin_can_delete():
    owner = User.objects.create_user(username="permission-delete-owner")
    maintainer = User.objects.create_user(username="permission-maintainer")
    member = User.objects.create_user(username="permission-member")
    other_member = User.objects.create_user(username="permission-other-member")
    space = make_team(owner)
    add_member(space, maintainer, SpaceMembership.Role.MAINTAINER)
    add_member(space, member, SpaceMembership.Role.USER)
    add_member(space, other_member, SpaceMembership.Role.USER)

    note = create_note(
        actor=member,
        space=space,
        note_key="delete-note",
        title="Member note",
        content="Member note.",
    )
    event = create_event(
        actor=member,
        space=space,
        event_key="delete-event",
        title="Member event",
        content="Member event.",
    )

    with pytest.raises(ChatAnalysisPermissionError):
        delete_note(actor=other_member, note=note)
    with pytest.raises(ChatAnalysisPermissionError):
        delete_event(actor=other_member, event=event)

    delete_note(actor=member, note=note)
    assert not Note.objects.filter(pk=note.pk).exists()

    delete_event(actor=maintainer, event=event)
    assert not Event.objects.filter(pk=event.pk).exists()


def test_event_assignment_requires_write_permission():
    owner = User.objects.create_user(username="permission-assign-owner")
    guest = User.objects.create_user(username="permission-assign-guest")
    space = make_team(owner)
    add_member(space, guest, SpaceMembership.Role.GUEST)
    note = create_note(
        actor=owner,
        space=space,
        note_key="assign-note",
        title="Note",
        content="Note.",
    )
    event = create_event(
        actor=owner,
        space=space,
        event_key="assign-event",
        title="Event",
        content="Event.",
    )

    with pytest.raises(ChatAnalysisPermissionError):
        assign_note_events(actor=guest, note=note, events=[event], manual=True)

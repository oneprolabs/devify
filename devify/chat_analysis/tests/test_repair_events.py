from datetime import timedelta
from io import StringIO

import pytest
from django.contrib.auth.models import User
from django.core.management import call_command
from django.utils import timezone

from chat_analysis.models import (Event, EventEvidence, EventRelation,
                                  EventTag, EventTagAssignment, QuestionAnswer,
                                  Report, ReportItem, ReportItemSource,
                                  ReportSection)
from chat_analysis.services import merge_events

from .test_event_identity import add_message, make_conversation, make_space

pytestmark = [pytest.mark.django_db, pytest.mark.integration]


@pytest.fixture
def event_factory():
    owner = User.objects.create_user(username="repair-owner")
    space = make_space(owner, "repair-space")

    def make_event(key, **fields):
        return Event.objects.create(
            space=space,
            created_by=owner,
            event_key=key,
            title="INC123 quote",
            content="Quote requested",
            **fields,
        )

    return owner, space, make_event


def test_merge_preserves_tags_relations_citations_and_window(event_factory):
    owner, space, make_event = event_factory
    later = timezone.now()
    earlier = later - timedelta(days=3)
    target = make_event("target", last_activity_at=later)
    source = make_event("source", opened_at=earlier)
    related = make_event("related")
    tag = EventTag.objects.create(
        space=space, created_by=owner, tag_key="customer", label="Customer"
    )
    assignment = EventTagAssignment.objects.create(
        event=source, tag=tag, created_by=owner
    )
    relation = EventRelation.objects.create(
        space=space,
        left_event=source,
        right_event=related,
        relation_kind=EventRelation.RelationKind.DEPENDS_ON,
        decision=EventRelation.Decision.ACCEPTED,
        created_by=owner,
    )
    answer = QuestionAnswer.objects.create(
        space=space,
        created_by=owner,
        question="What happened?",
        scope={"event_ids": [target.pk, source.pk]},
        citations=[
            {"kind": "event", "id": source.pk, "title": source.title},
            {"kind": "note", "id": source.pk},
        ],
    )
    report = Report.objects.create(
        space=space,
        created_by=owner,
        request_key="report",
        title="Report",
        body="Original report",
    )
    section = ReportSection.objects.create(
        report=report, section_key="events", title="Events", position=0
    )
    item = ReportItem.objects.create(
        section=section, position=0, title=source.title, summary=source.content
    )
    report_source = ReportItemSource.objects.create(
        item=item,
        reference_key=f"event:{source.pk}",
        source_kind=ReportItemSource.SourceKind.EVENT,
        event=source,
        event_snapshot={"id": source.pk, "title": source.title},
    )
    source_id = source.pk

    merge_events(actor=owner, source=source, target=target)

    assignment.refresh_from_db()
    relation.refresh_from_db()
    answer.refresh_from_db()
    target.refresh_from_db()
    assert not Event.objects.filter(pk=source_id).exists()
    assert assignment.event_id == target.pk
    assert (relation.left_event_id, relation.right_event_id) == (
        target.pk,
        related.pk,
    )
    assert relation.decision == EventRelation.Decision.ACCEPTED
    assert answer.citations == [
        {"kind": "event", "id": target.pk, "title": source.title},
        {"kind": "note", "id": source_id},
    ]
    assert answer.scope == {"event_ids": [target.pk]}
    report_source.refresh_from_db()
    assert report_source.event_id == target.pk
    assert report_source.event_snapshot == {
        "id": source_id,
        "title": source.title,
    }
    assert (target.opened_at, target.last_activity_at) == (earlier, later)


def test_repair_dry_run_discovers_shared_evidence_without_writing(
    event_factory,
):
    owner, space, make_event = event_factory
    first = make_event("quote-request")
    second = make_event("annual-pricing")
    separate = make_event("unrelated-pricing")
    conversation = make_conversation(space)
    message = add_message(conversation, 1, "Quote requested", timezone.now())
    for event in (first, second):
        EventEvidence.objects.create(
            event=event, message=message, created_by=owner
        )

    out = StringIO()
    call_command("repair_events", "--space", str(space.pk), stdout=out)
    assert "duplicate_rows=1" in out.getvalue()
    assert Event.objects.filter(space=space).count() == 3

    call_command(
        "repair_events", "--space", str(space.pk), "--apply", stdout=out
    )
    assert set(
        Event.objects.filter(space=space).values_list("pk", flat=True)
    ) == {
        first.pk,
        separate.pk,
    }


def test_repair_respects_decision_to_keep_events_separate(event_factory):
    owner, space, make_event = event_factory
    first = make_event("evt_inc123_quote")
    second = make_event("inc123-quote")
    EventRelation.objects.create(
        space=space,
        left_event=first,
        right_event=second,
        relation_kind=EventRelation.RelationKind.SEPARATE,
        decision=EventRelation.Decision.ACCEPTED,
        created_by=owner,
    )

    out = StringIO()
    call_command(
        "repair_events", "--space", str(space.pk), "--apply", stdout=out
    )
    assert "skipped_groups=1" in out.getvalue()
    assert set(
        Event.objects.filter(space=space).values_list("event_key", flat=True)
    ) == {
        "evt_inc123_quote",
        "inc123-quote",
    }

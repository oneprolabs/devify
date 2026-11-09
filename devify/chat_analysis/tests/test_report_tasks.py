from unittest.mock import patch

import pytest
from django.contrib.auth.models import User

from chat_analysis.models import Event, Note, Report
from chat_analysis.report_services import create_report_snapshot
from chat_analysis.report_tasks import generate_report_task
from spaces.models import Space, SpaceMembership

pytestmark = pytest.mark.django_db


def make_report(owner, slug="report-task-team"):
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
    return Report.objects.create(
        space=space,
        created_by=owner,
        request_key=f"{slug}-request",
        title="Task report",
        status=Report.Status.QUEUED,
        body="# Rule fallback",
        processing={"generator": "llm_pending"},
    )


def test_report_task_replaces_fallback_body_with_valid_llm_output():
    owner = User.objects.create_user(username="report-task-owner")
    report = make_report(owner)
    output = {
        "body": "# LLM report\n\nConfirmed follow-up.",
        "sections": [],
    }
    with patch(
        "chat_analysis.report_tasks.LLMTracker.call_and_track",
        return_value=(output, {"model": "test-model"}),
    ) as call:
        result = generate_report_task.run(report.pk)

    report.refresh_from_db()
    assert result["status"] == Report.Status.READY
    assert report.body == output["body"]
    assert report.processing["generator"] == "llm"
    call.assert_called_once()


def test_report_task_keeps_fallback_as_partial_when_llm_fails():
    owner = User.objects.create_user(username="report-task-failed")
    report = make_report(owner, "report-task-failed-team")
    with patch(
        "chat_analysis.report_tasks.LLMTracker.call_and_track",
        side_effect=RuntimeError("provider unavailable"),
    ):
        result = generate_report_task.run(report.pk)

    report.refresh_from_db()
    assert result["status"] == Report.Status.PARTIAL
    assert report.body == "# Rule fallback"
    assert report.processing["generator"] == "llm_failed"


def make_snapshot(owner, slug):
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
    event = Event.objects.create(
        space=space,
        created_by=owner,
        event_key="quote-event",
        title="Quote",
        content="Prepare quote.",
        status=Event.Status.OPEN,
    )
    note = Note.objects.create(
        space=space,
        created_by=owner,
        note_key="customer-note",
        title="Customer request",
        content="Annual pricing requested.",
    )
    report, _ = create_report_snapshot(
        actor=owner,
        space=space,
        request_key=f"{slug}-snapshot",
        title="Weekly report",
    )
    return report, event, note


def test_report_task_persists_generated_sections_and_keeps_sources():
    owner = User.objects.create_user(username="report-task-sections")
    report, event, note = make_snapshot(owner, "report-task-sections-team")
    output = {
        "body": "# Generated report",
        "sections": [
            {
                "section_key": "decisions",
                "title": "Decisions",
                "items": [
                    {
                        "title": "Quote",
                        "summary": "Prepare quote today.",
                        "label": "跟进",
                        "display_kind": "event",
                    }
                ],
            },
            {
                "section_key": "requests",
                "title": "Requests",
                "items": [
                    {
                        "title": "Customer request",
                        "summary": "Annual pricing requested.",
                        "display_kind": "note",
                    }
                ],
            },
        ],
    }
    with patch(
        "chat_analysis.report_tasks.LLMTracker.call_and_track",
        return_value=(output, {"model": "test-model"}),
    ):
        result = generate_report_task.run(report.pk)

    report.refresh_from_db()
    assert result["status"] == Report.Status.READY
    sections = list(report.sections.order_by("position"))
    assert [section.section_key for section in sections] == [
        "decisions",
        "requests",
    ]
    assert [section.title for section in sections] == ["Decisions", "Requests"]
    quote_item = sections[0].items.get()
    assert quote_item.summary == "Prepare quote today."
    assert quote_item.label == "跟进"
    assert quote_item.sources.get().event_id == event.pk
    request_item = sections[1].items.get()
    assert request_item.sources.get().note_id == note.pk
    assert report.content["item_count"] == 2
    assert report.content["llm_persisted"] is True


def test_report_task_keeps_snapshot_without_usable_sections():
    owner = User.objects.create_user(username="report-task-empty-sections")
    report, _, _ = make_snapshot(owner, "report-task-empty-sections-team")
    original_keys = list(
        report.sections.order_by("position").values_list(
            "section_key", flat=True
        )
    )
    output = {
        "body": "# Generated report",
        "sections": [
            "junk",
            {"title": ""},
            {"title": "No items", "items": "nope"},
        ],
    }
    with patch(
        "chat_analysis.report_tasks.LLMTracker.call_and_track",
        return_value=(output, {"model": "test-model"}),
    ):
        result = generate_report_task.run(report.pk)

    report.refresh_from_db()
    assert result["status"] == Report.Status.READY
    assert (
        list(
            report.sections.order_by("position").values_list(
                "section_key", flat=True
            )
        )
        == original_keys
    )
    assert report.content["llm_persisted"] is False
    assert report.content["item_count"] == 2

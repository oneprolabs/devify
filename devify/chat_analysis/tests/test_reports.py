import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from chat_analysis.models import Event, Note, Report
from spaces.models import Space, SpaceMembership

pytestmark = [pytest.mark.django_db, pytest.mark.integration]


def make_space(owner, slug):
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


def test_report_snapshot_freezes_event_and_note_content():
    owner = User.objects.create_user(username="report-owner")
    space = make_space(owner, "report-team")
    event = Event.objects.create(
        space=space,
        created_by=owner,
        event_key="event-1",
        title="Quote",
        content="Prepare quote.",
        status=Event.Status.OPEN,
    )
    note = Note.objects.create(
        space=space,
        created_by=owner,
        note_key="note-1",
        title="Customer request",
        content="Annual pricing requested.",
    )
    client = APIClient()
    client.force_authenticate(user=owner)

    response = client.post(
        f"/api/v1/spaces/{space.pk}/reports",
        {
            "request_key": "daily-2026-10-29",
            "title": "Daily report",
        },
        format="json",
    )
    assert response.status_code == 202
    report_id = response.data["data"]["id"]
    report = Report.objects.get(pk=report_id)
    assert report.content["event_count"] == 1
    assert report.content["note_count"] == 1
    assert report.body

    event.content = "Changed after report."
    event.save(update_fields=("content", "updated_at"))
    note.content = "Changed after report."
    note.save(update_fields=("content", "updated_at"))

    detail = client.get(f"/api/v1/reports/{report_id}")
    assert detail.status_code == 200
    sections = detail.data["data"]["sections"]
    summaries = [
        item["summary"] for section in sections for item in section["items"]
    ]
    assert "Prepare quote." in summaries
    assert "Annual pricing requested." in summaries
    assert "Changed after report." not in summaries


def test_report_request_key_is_idempotent_and_conflicts_on_changed_input():
    owner = User.objects.create_user(username="report-idempotent-owner")
    space = make_space(owner, "report-idempotent-team")
    client = APIClient()
    client.force_authenticate(user=owner)
    payload = {
        "request_key": "same-request",
        "title": "Report",
    }

    first = client.post(
        f"/api/v1/spaces/{space.pk}/reports", payload, format="json"
    )
    second = client.post(
        f"/api/v1/spaces/{space.pk}/reports", payload, format="json"
    )
    conflict = client.post(
        f"/api/v1/spaces/{space.pk}/reports",
        {**payload, "title": "Different"},
        format="json",
    )

    assert first.status_code == 202
    assert second.status_code == 200
    assert second.data["data"]["id"] == first.data["data"]["id"]
    assert conflict.status_code == 409
    assert Report.objects.filter(space=space).count() == 1


def test_guest_can_read_reports_but_cannot_create_one():
    owner = User.objects.create_user(username="report-guest-owner")
    guest = User.objects.create_user(username="report-guest")
    space = make_space(owner, "report-guest-team")
    SpaceMembership.objects.create(
        space=space,
        user=guest,
        role=SpaceMembership.Role.GUEST,
    )
    report = Report.objects.create(
        space=space,
        created_by=owner,
        request_key="guest-report",
        title="Existing",
        body="Frozen.",
        status=Report.Status.READY,
    )
    client = APIClient()
    client.force_authenticate(user=guest)

    assert client.get(f"/api/v1/spaces/{space.pk}/reports").status_code == 200
    assert client.get(f"/api/v1/reports/{report.pk}").status_code == 200
    assert (
        client.post(
            f"/api/v1/spaces/{space.pk}/reports",
            {"request_key": "guest-new", "title": "No"},
            format="json",
        ).status_code
        == 404
    )


def test_report_sources_survive_deletion():
    from chat_analysis.services import delete_event, delete_note

    owner = User.objects.create_user(username="report-delete-owner")
    space = make_space(owner, "report-delete-team")
    event = Event.objects.create(space=space, created_by=owner, event_key="event-delete", title="Event", content="Event original", status=Event.Status.OPEN)
    note = Note.objects.create(space=space, created_by=owner, note_key="note-delete", title="Note", content="Note original")
    client = APIClient()
    client.force_authenticate(user=owner)
    response = client.post(f"/api/v1/spaces/{space.pk}/reports", {"request_key": "delete-report", "title": "Report"}, format="json")
    report_id = response.data["data"]["id"]
    delete_event(actor=owner, event=event)
    delete_note(actor=owner, note=note)
    detail = client.get(f"/api/v1/reports/{report_id}")
    assert detail.status_code == 200
    sources = [source for section in detail.data["data"]["sections"] for item in section["items"] for source in item["sources"]]
    assert any(source["event_id"] is None and source["event_snapshot"] and source["event_snapshot"]["content"] == "Event original" for source in sources)
    assert any(source["note_id"] is None and source["note_snapshot"] and source["note_snapshot"]["content"] == "Note original" for source in sources)
    assert client.get(f"/api/v1/spaces/{space.pk}/reports").status_code == 200

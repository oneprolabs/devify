from unittest.mock import patch

import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from chat_analysis.models import (
    AnalysisJob,
    Event,
    EventNote,
    Note,
    NoteEvidence,
)
from chat_domain.models import Conversation, Message
from spaces.models import Space, SpaceMembership, SpaceTakeover

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


def make_conversation(space):
    return Conversation.objects.create(
        space=space,
        platform=Conversation.Platform.WECHAT,
        source_namespace="account:local",
        source_conversation_id="group-a",
        identity_key="wechat:account:local:group-a",
        title="Project group",
    )


def payload(conversation, request_key="job-1"):
    return {
        "conversation_id": conversation.pk,
        "request_key": request_key,
        "start_seq": 0,
        "end_seq": 10,
        "input_version": "wechat.v1",
        "specification": {"mode": "notes"},
    }


def test_member_can_create_and_query_analysis_job():
    owner = User.objects.create_user(username="analysis-api-owner")
    member = User.objects.create_user(username="analysis-api-member")
    space = make_space(owner, "analysis-api-team")
    SpaceMembership.objects.create(
        space=space,
        user=member,
        role=SpaceMembership.Role.USER,
    )
    conversation = make_conversation(space)
    client = APIClient()
    client.force_authenticate(user=member)

    with patch("chat_analysis.views.dispatch_analysis_job") as dispatch, patch(
        "chat_analysis.views.transaction.on_commit",
        side_effect=lambda callback: callback(),
    ):
        response = client.post(
            f"/api/v1/spaces/{space.pk}/analysis-jobs",
            payload(conversation),
            format="json",
        )
    assert response.status_code == 202
    dispatch.assert_called_once()
    job_id = response.data["data"]["id"]
    assert response.data["data"]["state"] == AnalysisJob.State.QUEUED

    listed = client.get(f"/api/v1/spaces/{space.pk}/analysis-jobs")
    assert listed.status_code == 200
    assert listed.data["data"]["list"][0]["id"] == job_id

    detail = client.get(f"/api/v1/analysis-jobs/{job_id}")
    assert detail.status_code == 200
    assert detail.data["data"]["conversation_id"] == conversation.pk


def test_same_request_key_is_idempotent_and_conflicts_on_changed_window():
    owner = User.objects.create_user(username="analysis-api-idempotent")
    space = make_space(owner, "analysis-api-idempotent-team")
    conversation = make_conversation(space)
    client = APIClient()
    client.force_authenticate(user=owner)

    with patch("chat_analysis.views.dispatch_analysis_job"), patch(
        "chat_analysis.views.transaction.on_commit",
        side_effect=lambda callback: callback(),
    ):
        first = client.post(
            f"/api/v1/spaces/{space.pk}/analysis-jobs",
            payload(conversation),
            format="json",
        )
        second = client.post(
            f"/api/v1/spaces/{space.pk}/analysis-jobs",
            payload(conversation),
            format="json",
        )
        conflict = client.post(
            f"/api/v1/spaces/{space.pk}/analysis-jobs",
            {**payload(conversation), "end_seq": 11},
            format="json",
        )

    assert first.status_code == 202
    assert second.status_code == 202
    assert second.data["data"]["id"] == first.data["data"]["id"]
    assert conflict.status_code == 409
    assert AnalysisJob.objects.filter(space=space).count() == 1


def test_non_member_cannot_create_or_read_analysis_job():
    owner = User.objects.create_user(username="analysis-api-isolation")
    outsider = User.objects.create_user(username="analysis-api-outsider")
    space = make_space(owner, "analysis-api-isolation-team")
    conversation = make_conversation(space)
    client = APIClient()
    client.force_authenticate(user=outsider)

    assert client.post(
        f"/api/v1/spaces/{space.pk}/analysis-jobs",
        payload(conversation),
        format="json",
    ).status_code == 404
    assert client.get(
        f"/api/v1/spaces/{space.pk}/analysis-jobs"
    ).status_code == 404


def test_failed_job_can_be_retried_by_member():
    owner = User.objects.create_user(username="analysis-api-retry")
    space = make_space(owner, "analysis-api-retry-team")
    conversation = make_conversation(space)
    job = AnalysisJob.objects.create(
        space=space,
        created_by=owner,
        conversation=conversation,
        request_key="retry-job",
        end_seq=10,
        input_version="wechat.v1",
        state=AnalysisJob.State.FAILED,
        error="temporary failure",
    )
    client = APIClient()
    client.force_authenticate(user=owner)
    with patch("chat_analysis.views.dispatch_analysis_job") as dispatch, patch(
        "chat_analysis.views.transaction.on_commit",
        side_effect=lambda callback: callback(),
    ):
        response = client.post(
            f"/api/v1/analysis-jobs/{job.pk}/retry",
            format="json",
        )
    assert response.status_code == 202
    dispatch.assert_called_once()
    job.refresh_from_db()
    assert job.state == AnalysisJob.State.QUEUED
    assert job.error == ""


def test_global_admin_needs_takeover_for_analysis_access():
    owner = User.objects.create_user(username="analysis-api-admin-owner")
    admin = User.objects.create_user(
        username="analysis-api-admin", is_staff=True
    )
    space = make_space(owner, "analysis-api-admin-team")
    conversation = make_conversation(space)
    job = AnalysisJob.objects.create(
        space=space,
        created_by=owner,
        conversation=conversation,
        request_key="admin-job",
        end_seq=1,
        input_version="wechat.v1",
    )
    client = APIClient()
    client.force_authenticate(user=admin)
    assert client.get(f"/api/v1/analysis-jobs/{job.pk}").status_code == 404
    SpaceTakeover.objects.create(space=space, admin=admin, reason="audit")
    assert client.get(f"/api/v1/analysis-jobs/{job.pk}").status_code == 200


def test_member_can_cancel_queued_analysis_job():
    owner = User.objects.create_user(username="cancel-analysis-owner")
    space = make_space(owner, "cancel-analysis-team")
    conversation = make_conversation(space)
    client = APIClient()
    client.force_authenticate(user=owner)
    with patch("chat_analysis.views.dispatch_analysis_job"), patch(
        "chat_analysis.views.transaction.on_commit", side_effect=lambda callback: callback()
    ):
        created = client.post(
            f"/api/v1/spaces/{space.pk}/analysis-jobs",
            payload(conversation),
            format="json",
        )
    assert created.status_code == 202
    job_id = created.data["data"]["id"]
    cancelled = client.post(f"/api/v1/analysis-jobs/{job_id}/cancel")
    assert cancelled.status_code == 200
    assert cancelled.data["data"]["state"] == "cancelled"


def test_events_can_be_filtered_by_source_conversation():
    owner = User.objects.create_user(username="events-filter-owner")
    space = make_space(owner, "events-filter-team")
    conversation = make_conversation(space)
    message = Message.objects.create(
        conversation=conversation,
        message_key="src:1",
        ingest_seq=1,
        sender_name="Alice",
    )
    note = Note.objects.create(
        space=space,
        created_by=owner,
        note_key="note-1",
        title="Quote note",
        content="Customer asked for the annual quote.",
    )
    NoteEvidence.objects.create(note=note, message=message)
    linked_event = Event.objects.create(
        space=space,
        created_by=owner,
        event_key="event-linked",
        title="Annual quote",
        content="Customer is waiting for the annual quote.",
    )
    EventNote.objects.create(event=linked_event, note=note, created_by=owner)
    unlinked_event = Event.objects.create(
        space=space,
        created_by=owner,
        event_key="event-unlinked",
        title="Unrelated matter",
        content="No evidence from this conversation.",
    )

    client = APIClient()
    client.force_authenticate(user=owner)
    url = f"/api/v1/spaces/{space.pk}/events"

    filtered = client.get(url, {"conversation_id": conversation.pk})
    assert filtered.status_code == 200
    ids = [row["id"] for row in filtered.data["data"]["list"]]
    assert ids == [linked_event.pk]
    assert unlinked_event.pk not in ids

    everything = client.get(url)
    assert everything.status_code == 200
    assert len(everything.data["data"]["list"]) == 2

    invalid = client.get(url, {"conversation_id": "abc"})
    assert invalid.status_code == 400

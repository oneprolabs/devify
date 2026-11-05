import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from chat_ingestion.models import UploadBatch
from spaces.models import Space, SpaceMembership

pytestmark = pytest.mark.django_db


def test_space_member_can_list_upload_batches():
    owner = User.objects.create_user(username="list-upload-owner")
    space = Space.objects.create(
        name="Upload list",
        slug="upload-list-team",
        kind=Space.Kind.TEAM,
        owner=owner,
    )
    SpaceMembership.objects.create(
        space=space, user=owner, role=SpaceMembership.Role.OWNER
    )
    UploadBatch.objects.create(
        space=space,
        uploaded_by=owner,
        source_type=UploadBatch.SourceType.WECHAT,
        idempotency_key="list-1",
        device_id="mac-device-1",
    )
    client = APIClient()
    client.force_authenticate(user=owner)

    response = client.get(
        f"/api/v1/spaces/{space.pk}/chat/uploads?page_size=1"
    )

    assert response.status_code == 200
    assert len(response.data["data"]["list"]) == 1
    assert response.data["data"]["pagination"]["page_size"] == 1
    row = response.data["data"]["list"][0]
    assert row["device_id"] == "mac-device-1"
    assert row["trigger"] == "manual"
    assert row["source_provider"] == ""
    assert row["conversation_count"] == 0
    assert row["image_count"] == 0
    assert row["analysis_summary"]["job_count"] == 0
    assert row["analysis_summary"]["state"] == ""


def test_list_reports_analysis_outcome():
    from chat_sources.models import Source

    from chat_analysis.models import (
        AnalysisJob,
        Event,
        EventNote,
        Note,
    )
    from chat_domain.models import Conversation

    owner = User.objects.create_user(username="analysis-list-owner")
    space = Space.objects.create(
        name="Analysis list",
        slug="analysis-list-team",
        kind=Space.Kind.TEAM,
        owner=owner,
    )
    SpaceMembership.objects.create(
        space=space, user=owner, role=SpaceMembership.Role.OWNER
    )
    source = Source.objects.create(
        space=space,
        channel_type=Source.ChannelType.WECHAT,
        provider="tauri_upload",
        external_account_key="analysis-account",
        display_name="Analysis account",
        created_by=owner,
        updated_by=owner,
    )
    batch = UploadBatch.objects.create(
        space=space,
        uploaded_by=owner,
        source=source,
        source_type=UploadBatch.SourceType.WECHAT,
        idempotency_key="analysis-batch",
        status=UploadBatch.Status.COMPLETED,
        message_count=3,
    )
    conversation = Conversation.objects.create(
        space=space,
        platform=Conversation.Platform.WECHAT,
        source_namespace="wechat-local",
        identity_key="wechat:wechat-local:analysis-conv",
        title="Analysis conversation",
    )
    job = AnalysisJob.objects.create(
        space=space,
        created_by=owner,
        conversation=conversation,
        request_key=f"upload:{batch.uuid}:{conversation.pk}",
        end_seq=10,
        input_version="wechat.v1",
        state=AnalysisJob.State.READY,
        attempts=2,
    )
    job.upload_batches.add(batch)
    note = Note.objects.create(
        space=space,
        created_by=owner,
        analysis_job=job,
        note_key=f"job:{job.uuid}:1-10",
        title="Note",
        content="Note body",
    )
    event = Event.objects.create(
        space=space,
        created_by=owner,
        event_key="evt_analysis_list",
        title="Event",
        content="Event body",
    )
    EventNote.objects.create(event=event, note=note, created_by=owner)

    client = APIClient()
    client.force_authenticate(user=owner)
    response = client.get(
        f"/api/v1/spaces/{space.pk}/chat/uploads?page_size=1"
    )

    assert response.status_code == 200
    row = response.data["data"]["list"][0]
    summary = row["analysis_summary"]
    assert row["source_provider"] == "tauri_upload"
    assert summary["state"] == "ready"
    assert summary["job_count"] == 1
    assert summary["event_count"] == 1
    assert summary["retried"] is True

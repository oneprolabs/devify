import io
import json
import uuid
from datetime import timedelta

import pytest
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from PIL import Image
from rest_framework.test import APIClient

from feedback.models import Feedback, FeedbackAttachment
from feedback.tasks import purge_feedback_attachments

pytestmark = pytest.mark.django_db


@pytest.fixture
def client(settings, tmp_path):
    settings.FEEDBACK_STORAGE_ROOT = str(tmp_path)
    user = User.objects.create_user(username="feedback-owner")
    api = APIClient()
    api.force_authenticate(user)
    return api


def screenshot():
    buffer = io.BytesIO()
    Image.new("RGB", (10, 10), "white").save(buffer, format="PNG")
    return SimpleUploadedFile("screen.png", buffer.getvalue(), "image/png")


def submit(client, **overrides):
    payload = {
        "client_id": str(uuid.uuid4()),
        "category": "upload",
        "description": "点击上传后显示服务不可用",
        "context": {"app_version": "0.1.0", "platform": "macos"},
    }
    payload.update(overrides)
    return client.post(
        "/api/v1/feedbacks",
        {"payload": json.dumps(payload), "screenshots": [screenshot()]},
        format="multipart",
    )


def test_submit_retry_and_changed_content_conflict(client):
    key = str(uuid.uuid4())
    diagnostics = {
        "schema_version": 1,
        "generated_at": "2026-11-13T09:00:00Z",
        "events": [
            {
                "at": "2026-11-13T09:00:00Z",
                "module": "upload",
                "operation": "failure",
                "code": "COMMAND_FAILED",
            }
        ],
    }
    first = submit(client, client_id=key, diagnostics=diagnostics)
    assert first.status_code == 201
    assert first.data["diagnostics"] == Feedback.objects.get().diagnostics
    assert first.data["diagnostics"]["events"][0]["code"] == "COMMAND_FAILED"
    second = submit(client, client_id=key, diagnostics=diagnostics)
    assert second.status_code == 200
    assert second.data["id"] == first.data["id"]
    assert Feedback.objects.count() == 1
    assert FeedbackAttachment.objects.count() == 1
    assert (
        submit(client, client_id=key, description="changed").status_code == 409
    )


def test_text_diagnostics_are_persisted_as_lines(client):
    key = str(uuid.uuid4())
    diagnostics = {
        "schema_version": 2,
        "generated_at": "2026-11-18T09:00:00Z",
        "lines": [
            "2026-11-18T09:00:00.000+08:00\tERROR\tauth.failure\t"
            "method=POST url=https://devify.test/api/v1/auth/login "
            "code=NETWORK_TIMEOUT"
        ],
    }
    response = submit(client, client_id=key, diagnostics=diagnostics)
    assert response.status_code == 201
    stored = Feedback.objects.get().diagnostics
    assert stored["schema_version"] == 2
    assert stored["lines"][0].endswith("code=NETWORK_TIMEOUT")
    assert response.data["diagnostics"] == stored


def test_feedback_and_private_attachment_are_owner_scoped(client):
    report = submit(client).data
    attachment_url = report["attachments"][0]["download_path"]
    assert client.get(attachment_url).status_code == 200
    other = User.objects.create_user(username="feedback-other")
    client.force_authenticate(other)
    assert client.get(f"/api/v1/feedbacks/{report['id']}").status_code == 404
    assert client.get(attachment_url).status_code == 404
    assert client.get("/api/v1/feedbacks").data["results"] == []
    client.force_authenticate(None)
    assert client.get(attachment_url).status_code == 401


def test_only_staff_can_reply_and_user_can_read_result(client):
    report = submit(client).data
    url = f"/api/v1/admin/feedbacks/{report['id']}"
    update = {"status": "resolved", "reply": "已修复", "fix_version": "0.1.1"}
    assert client.patch(url, update, format="json").status_code == 403
    staff = User.objects.create_user(username="support", is_staff=True)
    client.force_authenticate(staff)
    assert client.patch(url, update, format="json").status_code == 200
    client.force_authenticate(Feedback.objects.first().user)
    detail = client.get(f"/api/v1/feedbacks/{report['id']}").data
    assert detail["reply"] == "已修复"
    assert detail["fix_version"] == "0.1.1"
    assert detail["status"] == "resolved"


def test_diagnostics_whitelist_and_attachment_validation(client):
    assert (
        submit(
            client, diagnostics={"access_token": "do-not-store"}
        ).status_code
        == 400
    )
    assert submit(client, context={"chat_body": "private"}).status_code == 400
    bad = client.post(
        "/api/v1/feedbacks",
        {
            "payload": json.dumps(
                {
                    "client_id": str(uuid.uuid4()),
                    "category": "other",
                    "description": "bad",
                }
            ),
            "screenshots": SimpleUploadedFile(
                "fake.png", b"not-image", "image/png"
            ),
        },
        format="multipart",
    )
    assert bad.status_code == 400
    assert Feedback.objects.count() == 0


def test_attachment_expiry_removes_bytes_and_preserves_report(client):
    report = submit(client).data
    attachment = FeedbackAttachment.objects.get()
    path = attachment.path
    assert path.is_file()
    Feedback.objects.update(created_at=timezone.now() - timedelta(days=31))
    assert (
        client.get(report["attachments"][0]["download_path"]).status_code
        == 410
    )
    assert purge_feedback_attachments() == 1
    assert not path.exists()
    detail = client.get(f"/api/v1/feedbacks/{report['id']}").data
    assert detail["attachments"][0]["expired"] is True
    assert (
        client.get(detail["attachments"][0]["download_path"]).status_code
        == 410
    )

import io
import json
import uuid

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient

from feedback.serializers import CreateFeedbackSerializer
from feedback.views import validated_images


def payload():
    return {
        "client_id": str(uuid.uuid4()),
        "category": "upload",
        "description": "上传失败",
        "context": {
            "app_version": "0.1.0",
            "platform": "macos",
            "related_batch_ids": [42],
        },
        "diagnostics": {
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
        },
    }


def test_diagnostic_dates_are_serializable_after_validation():
    serializer = CreateFeedbackSerializer(data=payload())
    assert serializer.is_valid(), serializer.errors
    encoded = json.dumps(serializer.data)
    assert json.loads(encoded)["context"]["related_batch_ids"] == [42]


def test_request_correlation_survives_diagnostic_serialization():
    data = payload()
    data["diagnostics"]["events"][0].update(
        request_id="desktop-123",
        server_request_id="server-456",
        http_status=503,
    )
    serializer = CreateFeedbackSerializer(data=data)
    assert serializer.is_valid(), serializer.errors
    event = json.loads(json.dumps(serializer.data))["diagnostics"]["events"][0]
    assert event["request_id"] == "desktop-123"
    assert event["server_request_id"] == "server-456"
    assert event["http_status"] == 503


@pytest.mark.parametrize("field", ["request_id", "server_request_id"])
def test_request_correlation_rejects_invalid_ids(field):
    data = payload()
    data["diagnostics"]["events"][0][field] = "id\nprivate"
    assert not CreateFeedbackSerializer(data=data).is_valid()


@pytest.mark.parametrize(
    "key", ["chat_body", "access_token", "database", "settings"]
)
def test_unknown_diagnostic_fields_are_rejected(key):
    data = payload()
    data["diagnostics"][key] = "private"
    serializer = CreateFeedbackSerializer(data=data)
    assert not serializer.is_valid()


def test_image_content_is_reencoded_and_appended_data_removed():
    output = io.BytesIO()
    Image.new("RGB", (12, 8)).save(output, format="PNG")
    raw = output.getvalue() + b"private appended bytes"
    upload = SimpleUploadedFile("private-account-name.png", raw, "image/png")
    rows = validated_images([upload])
    assert len(rows) == 1
    assert b"private appended bytes" not in rows[0][1]
    assert Image.open(io.BytesIO(rows[0][1])).size == (12, 8)


@pytest.mark.parametrize(
    "content", [b"not a PNG", b"<svg><script>alert(1)</script></svg>"]
)
def test_fake_image_mime_is_rejected(content):
    with pytest.raises(ValidationError):
        validated_images(
            [SimpleUploadedFile("fake.png", content, "image/png")]
        )


def test_attachments_require_authentication_before_database_access():
    client = APIClient()
    url = f"/api/v1/feedbacks/{uuid.uuid4()}/attachments/{uuid.uuid4()}"
    assert client.get(url).status_code == 401
    assert client.get("/api/v1/admin/feedbacks").status_code == 401


def test_missing_attachment_bytes_return_expired_response(
    monkeypatch, tmp_path
):
    from types import SimpleNamespace

    from django.utils import timezone

    from feedback import views

    report = SimpleNamespace(created_at=timezone.now(), attachments=object())
    attachment = SimpleNamespace(expired=False, path=tmp_path / "removed.png")
    objects = iter([report, attachment])
    monkeypatch.setattr(views, "visible_reports", lambda *a, **kw: object())
    monkeypatch.setattr(
        views, "get_object_or_404", lambda *a, **kw: next(objects)
    )
    request = SimpleNamespace(user=SimpleNamespace(is_staff=False))
    response = views.AttachmentDownload().get(
        request, uuid.uuid4(), uuid.uuid4()
    )
    assert response.status_code == 410

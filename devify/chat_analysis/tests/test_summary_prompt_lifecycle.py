"""Real API lifecycle tests; external inference is always mocked."""

import uuid
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from chat_analysis.models import ChatSummary
from chat_analysis.summaries import prompts

pytestmark = [pytest.mark.django_db, pytest.mark.integration]


@pytest.fixture
def summary_api():
    user = get_user_model().objects.create_user(username="prompt-lifecycle")
    space = user.owned_spaces.get(kind="personal")
    client = APIClient()
    client.force_authenticate(user)
    now = timezone.now().replace(microsecond=0)
    snapshot = prompts.current_snapshot()
    payload = {
        "request_key": str(uuid.uuid4()),
        "platform": "wechat",
        "source_namespace": "test-account",
        "source_conversation_id": "test-chat",
        "title": "Test chat",
        "range_label": "Today",
        "mode": "time",
        "period_start": (now - timedelta(hours=1)).isoformat(),
        "period_end": now.isoformat(),
        "prompt_version": snapshot["version"],
        "prompt_digest": snapshot["sha256"],
        "messages": [
            {
                "username": "test-chat",
                "display": "Test chat",
                "sender": "Tester",
                "time": int(now.timestamp()) - 5,
                "text": "Delivery confirmed for Friday.",
            }
        ],
    }
    url = f"/api/v1/spaces/{space.pk}/chat-summaries"
    return client, url, payload


def test_creation_replay_retry_and_worker_keep_the_original_prompt(
    summary_api,
):
    from chat_analysis.summaries.tasks import generate_chat_summary

    client, url, payload = summary_api
    response = client.post(url, payload, format="json")
    assert response.status_code == 202, response.data
    pk = response.data["data"]["id"]
    record = ChatSummary.objects.get(pk=pk)
    snapshot = record.prompt_snapshot
    assert snapshot == prompts.current_snapshot()
    assert response.data["data"]["prompt_version"] == snapshot["version"]
    assert response.data["data"]["prompt_digest"] == snapshot["sha256"]
    assert "prompt_snapshot" not in response.data["data"]
    with patch.object(prompts, "TEMPLATE", "Updated business rules"):
        # A request-key replay succeeds even if its pinned version is old.
        replay = client.post(url, payload, format="json")
        assert replay.status_code == 200
        assert replay.data["data"]["id"] == pk
        ChatSummary.objects.filter(pk=pk).update(status="failed")
        retry = client.post(f"{url}/{pk}")
        assert retry.status_code == 202
        record.refresh_from_db()
        assert record.prompt_snapshot == snapshot
        with patch(
            "chat_analysis.summaries.tasks.LLMTracker.call_and_track",
            return_value=("## Result", {"model": "test"}),
        ) as model:
            generate_chat_summary.run(pk, str(record.dispatch_token))
        assert model.call_args.kwargs["prompt"] == prompts.cloud_prompt(
            snapshot
        )
    record.refresh_from_db()
    assert record.status == "ready"
    assert record.prompt_snapshot == snapshot


def test_new_request_rejects_stale_config_but_old_clients_still_work(
    summary_api,
):
    client, url, payload = summary_api
    incomplete = payload.copy()
    incomplete.pop("prompt_digest")
    assert client.post(url, incomplete, format="json").status_code == 400
    with patch.object(prompts, "TEMPLATE", "Updated business rules"):
        stale = client.post(url, payload, format="json")
        assert stale.status_code == 409
        assert stale.data["error_code"] == "summary_config_changed"
        assert not ChatSummary.objects.filter(
            request_key=payload["request_key"]
        ).exists()
        payload.pop("prompt_version")
        payload.pop("prompt_digest")
        created = client.post(url, payload, format="json")
        assert created.status_code == 202
        row = ChatSummary.objects.get(pk=created.data["data"]["id"])
        assert row.prompt_snapshot["template"] == "Updated business rules"


def test_configuration_revalidation_cannot_bypass_space_membership(
    summary_api,
):
    client, url, _ = summary_api
    config_url = url.replace("chat-summaries", "chat-summary-config")
    response = client.get(config_url, {"schema_version": 1})
    assert response.status_code == 200
    etag = response["ETag"]
    unchanged = client.get(
        config_url, {"schema_version": 1}, HTTP_IF_NONE_MATCH=etag
    )
    assert unchanged.status_code == 304
    assert unchanged.content == b""
    other = get_user_model().objects.create_user(username="prompt-outsider")
    client.force_authenticate(other)
    assert (
        client.get(
            config_url, {"schema_version": 1}, HTTP_IF_NONE_MATCH=etag
        ).status_code
        == 404
    )

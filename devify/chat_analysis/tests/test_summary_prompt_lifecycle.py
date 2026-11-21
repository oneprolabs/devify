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
from chat_analysis.summaries.input import summary_content
from chat_analysis.summaries.serializers import SummaryCreate
from chat_analysis.summaries.services import summary_input_hash

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
    updated = prompts.load_config()
    updated["template"] = "Updated business rules"
    updated["version"] = "test-update"
    with patch(
        "chat_analysis.summaries.views.load_config", return_value=updated
    ):
        # A request-key replay succeeds even if its pinned version is old.
        replay = client.post(url, payload, format="json")
        assert replay.status_code == 200
        assert replay.data["data"]["id"] == pk
        ChatSummary.objects.filter(pk=pk).update(status="failed")
        retry = client.post(f"{url}/{pk}")
        assert retry.status_code == 202
        record.refresh_from_db()
        assert record.prompt_snapshot == snapshot
        with (
            patch(
                "chat_analysis.summaries.tasks.LLMTracker.call_and_track",
                return_value=("## Result", {"model": "test"}),
            ) as model,
            patch(
                "chat_analysis.summaries.tasks.request_budget",
                return_value=(12000, lambda *_: 1),
            ),
        ):
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
    updated = prompts.load_config()
    updated["template"] = "Updated business rules"
    updated["version"] = "test-update"
    with patch(
        "chat_analysis.summaries.views.load_config", return_value=updated
    ):
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
    with patch(
        "chat_analysis.summaries.configuration.request_budget",
        return_value=(12000, None),
    ):
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


@pytest.mark.parametrize(
    "language,expected",
    [
        ("zh-CN", "zh-CN"),
        ("en-US", "en-US"),
        ("es", "es"),
        ("auto", "auto"),
        ("中文", "zh-CN"),
        ("English", "en-US"),
        ("按原文语言", "auto"),
    ],
)
def test_output_language_is_independent_of_client_ui_language(
    summary_api, language, expected
):
    import json

    client, url, payload = summary_api
    payload["language"] = language
    response = client.post(
        url, payload, format="json", HTTP_ACCEPT_LANGUAGE="es"
    )
    assert response.status_code == 202, response.data
    assert response.data["data"]["language"] == expected
    record = ChatSummary.objects.get(pk=response.data["data"]["id"])
    assert json.loads(summary_content(record))["language"] == expected


def test_account_language_changes_do_not_change_existing_tasks(summary_api):
    client, url, payload = summary_api
    user = get_user_model().objects.get(username="prompt-lifecycle")
    profile = user.profile
    profile.language = "es"
    profile.save(update_fields=["language"])
    client.force_authenticate(user)
    created = client.post(url, payload, format="json")
    assert created.status_code == 202
    assert created.data["data"]["language"] == "es"
    profile.language = "en-US"
    profile.save(update_fields=["language"])
    replay = client.post(url, payload, format="json")
    assert replay.status_code == 200
    assert replay.data["data"]["language"] == "es"
    assert replay.data["data"]["id"] == created.data["data"]["id"]
    payload["request_key"] = str(uuid.uuid4())
    next_task = client.post(url, payload, format="json")
    assert next_task.status_code == 202
    assert next_task.data["data"]["language"] == "en-US"


def test_legacy_implicit_language_replay_survives_configuration_failure(
    summary_api,
):
    client, url, payload = summary_api
    payload.pop("prompt_version")
    payload.pop("prompt_digest")
    created = client.post(url, payload, format="json")
    assert created.status_code == 202
    serializer = SummaryCreate(data=payload)
    assert serializer.is_valid()
    old_hash = summary_input_hash(
        {**serializer.validated_data, "language": "中文"}
    )
    pk = created.data["data"]["id"]
    ChatSummary.objects.filter(pk=pk).update(
        prompt_snapshot={}, input_hash=old_hash, language="中文"
    )
    with patch(
        "chat_analysis.summaries.views.load_config",
        side_effect=FileNotFoundError,
    ):
        replay = client.post(url, payload, format="json")
    assert replay.status_code == 200
    assert replay.data["data"]["id"] == pk
    assert replay.data["data"]["language"] == "中文"
    payload["language"] = "es"
    assert client.post(url, payload, format="json").status_code == 409

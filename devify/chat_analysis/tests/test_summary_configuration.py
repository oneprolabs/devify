"""Cache isolation, compatibility and budget contract without model calls."""

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from rest_framework.exceptions import NotFound
from rest_framework.test import APIRequestFactory, force_authenticate

from chat_analysis.summaries import configuration, prompts

URL = "/api/v1/spaces/00000000-0000-0000-0000-000000000001/"
URL += "chat-summary-config"


@pytest.fixture
def config_api(settings):
    settings.ALLOWED_HOSTS = ["*"]
    settings.CHAT_ANALYSIS_MODEL_INPUT_TOKENS = 12000
    with (
        patch.object(configuration, "summary_space") as access,
        patch.object(configuration, "build_entitlements") as grants,
        patch.object(
            configuration, "request_budget", return_value=(10000, None)
        ) as budget,
    ):
        access.return_value = SimpleNamespace(pk="space-1")
        grants.return_value = {
            "internal": False,
            "features": ["cloud.chat_summary"],
            "enforced": False,
        }

        def fetch(
            *,
            user_id=1,
            schema="1",
            authenticated=True,
            preferred="",
            **headers,
        ):
            request = APIRequestFactory().get(
                URL, {"schema_version": schema}, **headers
            )
            if authenticated:
                force_authenticate(
                    request,
                    user=SimpleNamespace(
                        pk=user_id,
                        is_authenticated=True,
                        profile=SimpleNamespace(language=preferred),
                    ),
                )
            return configuration.SummaryConfiguration.as_view()(
                request, space_id="space-1"
            )

        yield SimpleNamespace(
            fetch=fetch, access=access, grants=grants, budget=budget
        )


def test_configuration_contains_business_rules_and_conservative_budgets(
    config_api,
):
    response = config_api.fetch()
    assert response.status_code == 200
    data = response.data["data"]
    assert data["sha256"] == prompts.sha256(data["template"])
    assert data["template"] == prompts.current_snapshot()["template"]
    config = prompts.load_config()
    assert config["cloud_input_rules"] not in data["template"]
    assert data["variables"] == []
    assert data["languages"] == list(config["languages"])
    assert data["language_names"]["es"] == "Español"
    assert data["default_language"] == config["default_language"]
    assert data["default_scenario"] == "summary"
    assert data["max_instructions_chars"] == 4000
    scenarios = {item["id"]: item for item in data["scenarios"]}
    assert set(scenarios) == {
        "summary",
        "three_part",
        "action_items",
        "timeline",
        "custom",
    }
    assert scenarios["custom"]["requires_instructions"] is True
    for key, item in scenarios.items():
        assert item["sha256"] == prompts.sha256(item["template"])
        assert (
            item["template"]
            == prompts.current_snapshot(config, key)["template"]
        )
        assert item["budgets"]["cloud"]["prompt_bytes"] > len(
            item["template"].encode()
        )
    assert data["scope"]["capabilities"] == config_api.grants.return_value
    cloud = data["budgets"]["cloud"]
    assert cloud["max_request_bytes"] == 10000
    assert cloud["reserved_overhead_bytes"] == 64
    local = data["budgets"]["local_cli"]
    assert local["max_request_bytes"] == 12000
    assert local["reserved_overhead_bytes"] == 2048
    for budget in (cloud, local):
        assert budget["unit"] == "utf8_bytes"
        assert budget["max_content_bytes"] == (
            budget["max_request_bytes"]
            - budget["prompt_bytes"]
            - budget["reserved_overhead_bytes"]
        )
    assert response["Cache-Control"] == "private, no-cache"
    assert "Authorization" in response["Vary"]


@pytest.mark.parametrize("weak", [False, True])
def test_unchanged_configuration_has_no_body(config_api, weak):
    first = config_api.fetch()
    etag = first["ETag"]
    response = config_api.fetch(
        HTTP_IF_NONE_MATCH=f'"other", {"W/" if weak else ""}{etag}'
    )
    assert response.status_code == 304
    assert response.data is None
    assert response["ETag"] == etag


@pytest.mark.parametrize(
    "changed",
    ["user", "space", "server", "capabilities", "budget", "language"],
)
def test_context_or_budget_change_never_reuses_another_etag(
    config_api, changed
):
    etag = config_api.fetch()["ETag"]
    headers = {"HTTP_IF_NONE_MATCH": etag}
    if changed == "user":
        headers["user_id"] = 2
    elif changed == "space":
        config_api.access.return_value = SimpleNamespace(pk="space-2")
    elif changed == "server":
        headers["HTTP_HOST"] = "other.example"
    elif changed == "capabilities":
        config_api.grants.return_value["features"].append("ai.local_agent")
    elif changed == "language":
        headers["preferred"] = "es"
    else:
        config_api.budget.return_value = (9000, None)
    response = config_api.fetch(**headers)
    assert response.status_code == 200
    assert response["ETag"] != etag


def test_revoked_space_permission_cannot_return_304(config_api):
    etag = config_api.fetch()["ETag"]
    config_api.access.side_effect = NotFound("Space not found.")
    assert config_api.fetch(HTTP_IF_NONE_MATCH=etag).status_code == 404


def test_anonymous_or_unknown_schema_cannot_initialize(config_api):
    assert config_api.fetch(authenticated=False).status_code in (401, 403)
    assert config_api.fetch(schema="2").status_code == 400
    config_api.budget.assert_not_called()


def test_longer_template_reduces_content_allowance_without_truncation():
    short = configuration.input_budget(3000, "资料", 64)
    long = configuration.input_budget(3000, "资料" * 10, 64)
    assert short["max_content_bytes"] - long["max_content_bytes"] == 54
    assert configuration.input_budget(1, "资料", 64)["max_content_bytes"] == 0


@pytest.mark.parametrize("snapshot", [None, [], {"version": "broken"}])
def test_corrupt_snapshot_fails_instead_of_silently_using_current(snapshot):
    with pytest.raises(ValueError):
        prompts.cloud_prompt(snapshot)


def test_historical_snapshot_stays_frozen_after_current_template_changes():
    before = prompts.cloud_prompt({})
    with patch.object(prompts, "load_config", side_effect=FileNotFoundError):
        assert prompts.cloud_prompt({}) == before
        assert prompts.pinned_snapshot({})["version"] == "legacy-cloud-v1"

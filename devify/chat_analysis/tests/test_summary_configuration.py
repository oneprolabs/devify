"""Verify scoped catalogs, conditional downloads and provider independence."""

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from rest_framework.exceptions import NotFound
from rest_framework.test import APIRequestFactory, force_authenticate

from chat_analysis.summaries import configuration, prompts, views

URL = (
    "/api/v1/spaces/00000000-0000-0000-0000-000000000001/"
    "chat-summary-config"
)


@pytest.fixture
def config_api(settings):
    settings.ALLOWED_HOSTS = ["*"]
    settings.CHAT_ANALYSIS_MODEL_INPUT_TOKENS = 12000
    with (
        patch.object(views, "summary_space") as access,
        patch.object(configuration, "build_entitlements") as grants,
    ):
        access.return_value = SimpleNamespace(pk="space-1")
        grants.return_value = {
            "internal": False,
            "features": ["cloud.chat_summary"],
            "enforced": False,
        }

        def fetch(*, user_id=1, schema="1", authenticated=True, **headers):
            request = APIRequestFactory().get(
                URL, {"schema_version": schema}, **headers
            )
            if authenticated:
                force_authenticate(
                    request,
                    user=SimpleNamespace(pk=user_id, is_authenticated=True),
                )
            return views.SummaryConfiguration.as_view()(
                request, space_id="space-1"
            )

        yield SimpleNamespace(fetch=fetch, access=access, grants=grants)


def test_catalog_defaults_to_combined_analysis_with_per_scenario_budgets(
    config_api,
):
    response = config_api.fetch()
    assert response.status_code == 200
    data = response.data["data"]
    assert data["default_scenario"] == "three_part"
    assert data["max_instructions_chars"] == 4000
    scenarios = {item["id"]: item for item in data["scenarios"]}
    assert set(scenarios) == {
        "summary",
        "three_part",
        "action_items",
        "timeline",
        "custom",
    }
    assert scenarios["three_part"]["name"] == "综合分析"
    assert scenarios["custom"]["requires_instructions"] is True
    config = prompts.load_config()
    for key, item in scenarios.items():
        snapshot = prompts.current_snapshot(config, key)
        assert item["sha256"] == prompts.sha256(item["template"])
        assert item["template"] == snapshot["template"]
        assert config["cloud_input_rules"] not in item["template"]
        for engine, reserve in (("cloud", 64), ("local_cli", 2048)):
            budget = item["budgets"][engine]
            assert budget["unit"] == "utf8_bytes"
            assert budget["max_request_bytes"] == 12000
            assert budget["reserved_overhead_bytes"] == reserve
            assert budget["max_content_bytes"] == max(
                0, 12000 - budget["prompt_bytes"] - reserve
            )
    assert data["scope"]["capabilities"] == config_api.grants.return_value
    assert response["Cache-Control"] == "private, no-cache"
    assert "Authorization" in response["Vary"]


def test_catalog_download_does_not_initialize_or_call_a_model(config_api):
    with patch(
        "chat_analysis.token_budget.request_budget",
        side_effect=AssertionError("Catalog download must be provider-free"),
    ):
        assert config_api.fetch().status_code == 200


@pytest.mark.parametrize("weak", [False, True])
def test_unchanged_catalog_has_no_body(config_api, weak):
    etag = config_api.fetch()["ETag"]
    response = config_api.fetch(
        HTTP_IF_NONE_MATCH=f'"other", {"W/" if weak else ""}{etag}'
    )
    assert response.status_code == 304
    assert response.data is None
    assert response["ETag"] == etag


@pytest.mark.parametrize(
    "changed", ["user", "space", "server", "capabilities", "budget"]
)
def test_context_or_budget_change_cannot_reuse_another_etag(
    config_api, settings, changed
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
    else:
        settings.CHAT_ANALYSIS_MODEL_INPUT_TOKENS = 11000
    response = config_api.fetch(**headers)
    assert response.status_code == 200
    assert response["ETag"] != etag


def test_ui_language_does_not_require_another_system_template(config_api):
    etag = config_api.fetch()["ETag"]
    response = config_api.fetch(
        HTTP_IF_NONE_MATCH=etag, HTTP_ACCEPT_LANGUAGE="en-US"
    )
    assert response.status_code == 304


def test_revoked_space_permission_cannot_return_304(config_api):
    etag = config_api.fetch()["ETag"]
    config_api.access.side_effect = NotFound("Space not found.")
    assert config_api.fetch(HTTP_IF_NONE_MATCH=etag).status_code == 404


def test_anonymous_or_unknown_schema_cannot_initialize(config_api):
    assert config_api.fetch(authenticated=False).status_code in (401, 403)
    assert config_api.fetch(schema="2").status_code == 400
    config_api.grants.assert_not_called()


def test_longer_template_reduces_content_allowance_without_truncation():
    short = configuration.input_budget(3000, "资料", 64)
    long = configuration.input_budget(3000, "资料" * 10, 64)
    assert short["max_content_bytes"] - long["max_content_bytes"] == 54
    assert configuration.input_budget(1, "资料", 64)["max_content_bytes"] == 0

"""Scenario composition is independent of user instructions and language."""

import json
from types import SimpleNamespace

import pytest
import yaml

from chat_analysis.summaries.input import summary_content
from chat_analysis.summaries.prompts import (
    cloud_prompt,
    current_snapshot,
    load_config,
)


@pytest.mark.parametrize(
    "scenario", ["summary", "three_part", "action_items", "timeline", "custom"]
)
def test_one_common_template_plus_selected_scenario(scenario):
    config = load_config()
    snapshot = current_snapshot(config, scenario)
    assert snapshot["scenario"] == scenario
    assert snapshot["template"].startswith(config["template"] + "\n\n")
    assert snapshot["template"].endswith(
        config["scenarios"][scenario]["prompt"]
    )
    assert "\n## 总结" in current_snapshot(config, "three_part")["template"]
    assert "\n## 总结" not in current_snapshot(config, "custom")["template"]


def test_user_instructions_stay_outside_the_system_prompt_and_count_as_input():
    snapshot = current_snapshot()
    before = cloud_prompt(snapshot)
    record = SimpleNamespace(
        title="Test",
        range_label="Today",
        language="es",
        input_messages=[],
        prompt_snapshot=snapshot,
    )
    plain = summary_content(record)
    extra = "Only compare the delivery commitments. " * 20
    snapshot["user_instructions"] = extra
    content = summary_content(record)
    assert cloud_prompt(snapshot) == before
    assert json.loads(content)["instructions"] == extra
    assert json.loads(content)["language"] == "es"
    assert len(content.encode()) > len(plain.encode()) + len(extra.encode())


@pytest.mark.parametrize(
    "change",
    [
        {"scenarios": {}},
        {"default_scenario": "missing"},
        {"scenarios": {"broken": {"name": "Missing prompt"}}},
    ],
)
def test_invalid_scenario_configuration_is_rejected(
    change, tmp_path, settings
):
    config = {**load_config(), **change}
    path = tmp_path / "summary.yaml"
    path.write_text(yaml.safe_dump(config), encoding="utf-8")
    settings.CHAT_SUMMARY_CONFIG_PATH = str(path)
    with pytest.raises(ValueError):
        load_config()

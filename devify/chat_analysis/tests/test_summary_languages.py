"""Language selection and prompt changes are driven by configuration data."""

from types import SimpleNamespace

import pytest
import yaml

from chat_analysis.summaries import prompts


@pytest.mark.parametrize(
    "requested,preferred,expected",
    [
        ("es", "zh-CN", "es"),
        ("EN-us", "es", "en-US"),
        ("auto", "en-US", "auto"),
        ("中文", "es", "zh-CN"),
        ("English", "es", "en-US"),
        ("按原文语言", "es", "auto"),
        (None, "es", "es"),
        (None, "unknown", "en-US"),
    ],
)
def test_explicit_language_then_account_preference_then_default(
    requested, preferred, expected
):
    user = SimpleNamespace(profile=SimpleNamespace(language=preferred))
    assert (
        prompts.summary_language(requested, user, prompts.load_config())
        == expected
    )


def test_unknown_language_is_rejected_instead_of_silently_becoming_chinese():
    with pytest.raises(ValueError, match="Unsupported"):
        prompts.summary_language("unknown", object(), prompts.load_config())


def test_configuration_update_adds_languages_without_changing_python(
    tmp_path, settings
):
    config = prompts.load_config()
    original = prompts.current_snapshot(config)
    config["version"] = "test-french-support"
    config["languages"]["fr-FR"] = "Français"
    config["template"] += "\nConfiguration update."
    path = tmp_path / "summary.yaml"
    path.write_text(yaml.safe_dump(config), encoding="utf-8")
    settings.CHAT_SUMMARY_CONFIG_PATH = str(path)
    loaded = prompts.load_config()
    assert prompts.summary_language("fr-FR", object(), loaded) == "fr-FR"
    assert prompts.current_snapshot()["version"] == "test-french-support"
    assert prompts.current_snapshot()["sha256"] != original["sha256"]
    assert prompts.cloud_prompt(original).startswith(original["template"])


@pytest.mark.parametrize(
    "change",
    [
        {"template": ""},
        {"default_language": "unknown"},
        {"languages": {"<script>": "bad"}},
        {"language_aliases": {"legacy": "unknown"}},
    ],
)
def test_invalid_configuration_is_not_served_as_a_valid_update(
    change, tmp_path, settings
):
    config = {**prompts.load_config(), **change}
    path = tmp_path / "summary.yaml"
    path.write_text(yaml.safe_dump(config), encoding="utf-8")
    settings.CHAT_SUMMARY_CONFIG_PATH = str(path)
    with pytest.raises(ValueError):
        prompts.load_config()

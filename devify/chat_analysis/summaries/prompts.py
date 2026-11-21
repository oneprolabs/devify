"""Load versioned summary rules; keep task snapshots independent of updates."""

import hashlib
import re
from pathlib import Path

import yaml
from django.conf import settings

LEGACY_PATH = (
    Path(__file__).resolve().parents[2]
    / "conf"
    / "chat_analysis"
    / "legacy-cloud-v1.txt"
)


def sha256(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_config():
    with open(settings.CHAT_SUMMARY_CONFIG_PATH, encoding="utf-8") as source:
        config = yaml.safe_load(source)
    if not isinstance(config, dict):
        raise ValueError("Invalid summary configuration.")
    for field in ("version", "template", "cloud_input_rules"):
        if not isinstance(config.get(field), str) or not config[field].strip():
            raise ValueError(f"Invalid summary configuration: {field}.")
    languages = config.get("languages")
    if (
        len(config["version"]) > 80
        or not isinstance(languages, dict)
        or not languages
        or any(
            not isinstance(code, str)
            or len(code) > 30
            or not re.fullmatch(r"[a-z]{2,3}(?:-[A-Za-z0-9]{2,8})*|auto", code)
            or not isinstance(label, str)
            or not label.strip()
            for code, label in languages.items()
        )
        or not isinstance(config.get("default_language"), str)
        or config["default_language"] not in languages
    ):
        raise ValueError("Invalid summary language configuration.")
    aliases = config.get("language_aliases", {})
    if not isinstance(aliases, dict) or any(
        not isinstance(alias, str)
        or not isinstance(target, str)
        or target not in languages
        for alias, target in aliases.items()
    ):
        raise ValueError("Invalid summary language aliases.")
    scenarios = config.get("scenarios")
    if not isinstance(scenarios, dict) or not scenarios:
        raise ValueError("Missing summary scenarios.")
    for key, scenario in scenarios.items():
        if (
            not isinstance(key, str)
            or not re.fullmatch(r"[a-z][a-z0-9_]{0,39}", key)
            or not isinstance(scenario, dict)
            or any(
                not isinstance(scenario.get(field), str)
                or not scenario[field].strip()
                for field in ("name", "description", "prompt")
            )
            or not isinstance(
                scenario.get("requires_instructions", False), bool
            )
        ):
            raise ValueError("Invalid summary scenario.")
    if (
        not isinstance(config.get("default_scenario"), str)
        or config["default_scenario"] not in scenarios
    ):
        raise ValueError("Invalid default summary scenario.")
    return config


def summary_language(language, user, config):
    """Resolve one task's explicit language, then account, then default."""
    lookup = {code.casefold(): code for code in config["languages"]}
    lookup.update(
        (alias.casefold(), code)
        for alias, code in config.get("language_aliases", {}).items()
    )
    if language is None:
        profile = getattr(user, "profile", None)
        preferred = getattr(profile, "language", "") or ""
        return lookup.get(preferred.casefold(), config["default_language"])
    resolved = lookup.get(language.casefold())
    if resolved is None:
        raise ValueError("Unsupported summary output language.")
    return resolved


def current_snapshot(config=None, scenario=None):
    config = load_config() if config is None else config
    scenario = config["default_scenario"] if scenario is None else scenario
    if scenario not in config["scenarios"]:
        raise ValueError("Unsupported summary scenario.")
    template = "\n\n".join(
        (config["template"], config["scenarios"][scenario]["prompt"])
    )
    return {
        "version": config["version"],
        "sha256": sha256(template),
        "template": template,
        "cloud_input_rules": config["cloud_input_rules"],
        "scenario": scenario,
        "user_instructions": "",
    }


def pinned_snapshot(snapshot):
    if snapshot == {}:
        template = LEGACY_PATH.read_text(encoding="utf-8").rstrip("\n")
        return {
            "version": "legacy-cloud-v1",
            "sha256": sha256(template),
            "template": template,
            "cloud_input_rules": "",
        }
    if (
        not isinstance(snapshot, dict)
        or not isinstance(snapshot.get("version"), str)
        or not snapshot["version"]
        or not isinstance(snapshot.get("template"), str)
        or not snapshot["template"]
        or not isinstance(snapshot.get("cloud_input_rules"), str)
        or not isinstance(snapshot.get("user_instructions", ""), str)
        or snapshot.get("sha256") != sha256(snapshot["template"])
    ):
        raise ValueError("Invalid pinned summary prompt.")
    return snapshot


def cloud_prompt(snapshot):
    pinned = pinned_snapshot(snapshot)
    return "\n".join(
        part
        for part in (pinned["template"], pinned["cloud_input_rules"])
        if part
    )

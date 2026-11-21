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
    """Return the SHA-256 of an exact UTF-8 string."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_config():
    """Read and validate the versioned system rules and scenario catalog."""
    with open(settings.CHAT_SUMMARY_CONFIG_PATH, encoding="utf-8") as source:
        config = yaml.safe_load(source)
    if not isinstance(config, dict):
        raise ValueError("Invalid summary configuration.")
    for field in ("version", "template", "cloud_input_rules"):
        if not isinstance(config.get(field), str) or not config[field].strip():
            raise ValueError(f"Invalid summary configuration: {field}.")
    if len(config["version"]) > 80:
        raise ValueError("Summary prompt version is too long.")
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


def current_snapshot(config=None, scenario=None):
    """Compose immutable system rules for one selected scenario."""
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
    """Validate stored rules, preserving pre-migration task behavior."""
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
    """Append cloud input framing to the stored business template."""
    pinned = pinned_snapshot(snapshot)
    return "\n".join(
        part
        for part in (pinned["template"], pinned["cloud_input_rules"])
        if part
    )

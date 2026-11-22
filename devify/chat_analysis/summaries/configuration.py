"""Build the versioned catalog and lightweight desktop update hints."""

from django.conf import settings

from billing.entitlements import build_entitlements
from chat_analysis.summaries.prompts import (
    cloud_prompt,
    current_snapshot,
    load_config,
)

CHECK_INTERVAL = 21600
RETRY_INTERVAL = 900


def prompt_metadata(config=None):
    """A public change hint, never a scoped cache or an entitlement grant."""
    config = load_config() if config is None else config
    return {
        "schema_version": 1,
        "version": config["version"],
        "min_check_interval_seconds": CHECK_INTERVAL,
    }


def input_budget(limit, prompt, reserved):
    """Expose the configured byte ceiling minus template and framing costs."""
    prompt_bytes = len(prompt.encode("utf-8"))
    return {
        "unit": "utf8_bytes",
        "max_request_bytes": max(0, limit),
        "prompt_bytes": prompt_bytes,
        "reserved_overhead_bytes": reserved,
        "max_content_bytes": max(0, limit - prompt_bytes - reserved),
    }


def scenario_configuration(config, key, input_limit):
    """Describe one scenario and the cost of its fully composed template."""
    snapshot = current_snapshot(config, key)
    scenario = config["scenarios"][key]
    return {
        "id": key,
        "name": scenario["name"],
        "description": scenario["description"],
        "requires_instructions": scenario.get("requires_instructions", False),
        "template": snapshot["template"],
        "sha256": snapshot["sha256"],
        "budgets": {
            "cloud": input_budget(input_limit, cloud_prompt(snapshot), 64),
            "local_cli": input_budget(input_limit, snapshot["template"], 2048),
        },
    }


def build_configuration(user, space, server):
    """Build a scoped cache payload without contacting any model provider."""
    config = load_config()
    input_limit = int(
        getattr(settings, "CHAT_ANALYSIS_MODEL_INPUT_TOKENS", 12000)
    )
    entitlements = build_entitlements(user)
    return {
        **prompt_metadata(config),
        "scope": {
            "server": server,
            "account_id": str(user.pk),
            "space_id": str(space.pk),
            "capabilities": {
                "enforced": entitlements["enforced"],
                "features": sorted(entitlements["features"]),
                "internal": entitlements["internal"],
            },
        },
        "default_scenario": config["default_scenario"],
        "scenarios": [
            scenario_configuration(config, key, input_limit)
            for key in config["scenarios"]
        ],
        "max_instructions_chars": 4000,
        "output_format": "markdown",
        "retry_after_seconds": RETRY_INTERVAL,
        "no_cache_behavior": "require_online_initialization",
    }

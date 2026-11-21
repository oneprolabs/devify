"""Authenticated initialization and conditional checks for desktop caches."""

import json

from django.conf import settings
from django.utils.cache import patch_vary_headers
from django.utils.http import parse_etags
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from billing.entitlements import build_entitlements
from chat_analysis.summaries.prompts import (
    cloud_prompt,
    current_snapshot,
    load_config,
    sha256,
    summary_language,
)
from chat_analysis.summaries.views import summary_space
from chat_analysis.token_budget import request_budget

CHECK_INTERVAL = 21600
RETRY_INTERVAL = 900


def prompt_metadata(snapshot=None):
    """A public change hint, never a scoped cache or an entitlement grant."""
    snapshot = current_snapshot() if snapshot is None else snapshot
    return {
        "schema_version": 1,
        "version": snapshot["version"],
        "sha256": snapshot["sha256"],
        "min_check_interval_seconds": CHECK_INTERVAL,
    }


def input_budget(limit, prompt, reserved):
    prompt_bytes = len(prompt.encode("utf-8"))
    return {
        "unit": "utf8_bytes",
        "max_request_bytes": max(0, limit),
        "prompt_bytes": prompt_bytes,
        "reserved_overhead_bytes": reserved,
        "max_content_bytes": max(0, limit - prompt_bytes - reserved),
    }


class SummaryConfiguration(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, space_id):
        # Permission checks must precede conditional responses as well.
        space = summary_space(request.user, space_id)
        if request.query_params.get("schema_version") != "1":
            return Response(
                {"detail": "Unsupported summary configuration schema."},
                status=400,
            )
        config = load_config()
        snapshot = current_snapshot(config)
        configured = int(
            getattr(settings, "CHAT_ANALYSIS_MODEL_INPUT_TOKENS", 12000)
        )
        cloud_limit, _ = request_budget(configured)
        entitlements = build_entitlements(request.user)
        data = {
            **prompt_metadata(snapshot),
            "scope": {
                "server": request.build_absolute_uri("/").rstrip("/"),
                "account_id": str(request.user.pk),
                "space_id": str(space.pk),
                "capabilities": {
                    "enforced": entitlements["enforced"],
                    "features": sorted(entitlements["features"]),
                    "internal": entitlements["internal"],
                },
            },
            "template": snapshot["template"],
            "variables": [],
            "languages": list(config["languages"]),
            "language_names": config["languages"],
            "default_language": summary_language(None, request.user, config),
            "output_format": "markdown",
            "budgets": {
                "cloud": input_budget(cloud_limit, cloud_prompt(snapshot), 64),
                "local_cli": input_budget(
                    configured, snapshot["template"], 2048
                ),
            },
            "retry_after_seconds": RETRY_INTERVAL,
            "no_cache_behavior": "require_online_initialization",
        }
        etag = '"{}"'.format(
            sha256(json.dumps(data, sort_keys=True, ensure_ascii=False))
        )
        candidates = parse_etags(request.headers.get("If-None-Match", ""))
        unchanged = "*" in candidates or etag in [
            value.removeprefix("W/") for value in candidates
        ]
        response = Response(
            None if unchanged else {"data": data},
            status=304 if unchanged else 200,
        )
        response["ETag"] = etag
        response["Cache-Control"] = "private, no-cache"
        patch_vary_headers(response, ("Authorization", "Cookie"))
        return response

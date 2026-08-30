"""
Registry for application-center entries.

Apps register one metadata row from their ``AppConfig.ready()``. The apps
API renders the registry instead of a hardcoded list, so adding a new
application no longer means editing another app's views.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class AppRegistry:
    """In-process registry of application-center entries."""

    def __init__(self):
        self._apps: dict[str, dict] = {}

    def register(
        self,
        *,
        key: str,
        name,
        name_zh,
        path: str,
        description,
        order: int = 100,
    ) -> None:
        """Register or replace one application entry."""
        if key in self._apps:
            logger.debug("App entry %s re-registered", key)
        self._apps[key] = {
            "key": key,
            "name": name,
            "name_zh": name_zh,
            "path": path,
            "description": description,
            "order": order,
        }

    def list_apps(self) -> list[dict]:
        """Return registered entries ordered for display."""
        return [
            {k: v for k, v in app.items() if k != "order"}
            for app in sorted(
                self._apps.values(),
                key=lambda item: (item["order"], item["key"]),
            )
        ]


APP_REGISTRY = AppRegistry()

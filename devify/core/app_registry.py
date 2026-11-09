"""
Registry for application-center entries.

Apps register one metadata row from their ``AppConfig.ready()``. The apps
API renders the registry instead of a hardcoded list, so adding a new
application no longer means editing another app's views.

An entry may also carry a ``stats`` callable. The app centre draws a few
live numbers on each card, and the app that owns the data is the only place
that knows how to count them; the callable returns plain numbers under
stable keys, and the frontend supplies the wording.
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
        stats=None,
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
            "stats": stats,
        }

    def list_apps(self, user=None) -> list[dict]:
        """
        Return registered entries ordered for display.

        With a user, each entry also carries that user's counts. One app
        failing to count must not blank the whole app centre, so a broken
        ``stats`` callable logs and yields no numbers for that card.
        """
        entries = []
        for app in sorted(
            self._apps.values(),
            key=lambda item: (item["order"], item["key"]),
        ):
            entry = {
                k: v for k, v in app.items() if k not in ("order", "stats")
            }
            entry["stats"] = self._read_stats(app, user)
            entries.append(entry)
        return entries

    @staticmethod
    def _read_stats(app: dict, user) -> dict:
        counter = app.get("stats")
        if not counter or user is None:
            return {}

        try:
            return counter(user) or {}
        except Exception:
            logger.exception("App %s failed to report stats", app["key"])
            return {}


APP_REGISTRY = AppRegistry()

"""
Unit tests for the app-centre registry's per-user stats.
"""

import pytest

from core.app_registry import AppRegistry


class FakeUser:
    pk = 1


def _register(registry, **kwargs):
    registry.register(
        key=kwargs.pop("key", "demo"),
        name="Demo",
        name_zh="演示",
        path="/apps/demo",
        description="",
        **kwargs,
    )


@pytest.mark.unit
class TestAppRegistryStats:
    def test_entries_carry_the_users_numbers(self):
        registry = AppRegistry()
        _register(registry, stats=lambda user: {"open": 3})

        entry = registry.list_apps(FakeUser())[0]

        assert entry["stats"] == {"open": 3}
        assert "order" not in entry

    def test_no_user_means_no_numbers(self):
        registry = AppRegistry()
        _register(registry, stats=lambda user: {"open": 3})

        assert registry.list_apps()[0]["stats"] == {}

    def test_an_app_without_a_counter_reports_nothing(self):
        registry = AppRegistry()
        _register(registry)

        assert registry.list_apps(FakeUser())[0]["stats"] == {}

    def test_one_broken_counter_does_not_blank_the_others(self):
        registry = AppRegistry()

        def explode(user):
            raise RuntimeError("no database today")

        _register(registry, key="broken", stats=explode, order=1)
        _register(registry, key="fine", stats=lambda user: {"open": 1}, order=2)

        entries = {app["key"]: app["stats"] for app in registry.list_apps(FakeUser())}

        assert entries["broken"] == {}
        assert entries["fine"] == {"open": 1}

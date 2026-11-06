"""Unit tests for the application-center registry."""

import pytest

from core.app_registry import AppRegistry


pytestmark = pytest.mark.unit


class TestAppRegistry:
    def test_entries_are_ordered_then_keyed(self):
        registry = AppRegistry()
        registry.register(
            key="zeta",
            name="Zeta",
            name_zh="Z",
            path="/apps/zeta",
            description="z",
            order=10,
        )
        registry.register(
            key="alpha",
            name="Alpha",
            name_zh="A",
            path="/apps/alpha",
            description="a",
            order=10,
        )
        registry.register(
            key="first",
            name="First",
            name_zh="F",
            path="/apps/first",
            description="f",
            order=1,
        )

        keys = [app["key"] for app in registry.list_apps()]
        assert keys == ["first", "alpha", "zeta"]

    def test_order_is_not_exposed_to_clients(self):
        registry = AppRegistry()
        registry.register(
            key="relay",
            name="Relay",
            name_zh="投递",
            path="/apps/relay",
            description="d",
        )

        entry = registry.list_apps()[0]
        # `order` is how the registry sorts; `stats` is the callable, not the
        # numbers. Clients see the numbers under "stats", never the function.
        assert "order" not in entry
        assert set(entry) == {
            "key",
            "name",
            "name_zh",
            "path",
            "description",
            "stats",
            "space_kinds",
        }
        assert entry["stats"] == {}

    def test_re_registering_replaces_instead_of_duplicating(self):
        registry = AppRegistry()
        registry.register(
            key="relay",
            name="Old",
            name_zh="旧",
            path="/apps/relay",
            description="d",
        )
        registry.register(
            key="relay",
            name="New",
            name_zh="新",
            path="/apps/relay",
            description="d",
        )

        apps = registry.list_apps()
        assert len(apps) == 1
        assert apps[0]["name"] == "New"


class TestRegisteredApps:
    def test_relay_and_expense_are_both_registered(self):
        from core.app_registry import APP_REGISTRY

        keys = [app["key"] for app in APP_REGISTRY.list_apps()]
        assert "relay" in keys
        assert "expense" in keys


def test_scope_filters_before_reading_stats():
    registry = AppRegistry()
    counter = lambda user: pytest.fail("personal stats must not be read in team context")
    registry.register(key="expense", name="Expense", name_zh="发票", path="/expense", description="", space_kinds=("personal",), stats=counter)
    registry.register(key="team", name="Team", name_zh="团队", path="/team", description="", space_kinds=("team",))
    registry.register(key="both", name="Both", name_zh="通用", path="/both", description="", space_kinds=("personal", "team"))
    registry.register(key="legacy", name="Legacy", name_zh="旧应用", path="/legacy", description="")
    assert {item["key"] for item in registry.list_apps(user=object(), space_kind="team")} == {"team", "both"}
    assert {item["key"] for item in registry.list_apps(space_kind="personal")} == {"expense", "both", "legacy"}


def test_invalid_scope_is_rejected():
    with pytest.raises(ValueError):
        AppRegistry().register(key="bad", name="Bad", name_zh="坏", path="/bad", description="", space_kinds=("unknown",))

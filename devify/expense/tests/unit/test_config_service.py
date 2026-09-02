"""Unit tests for expense configuration services."""

import pytest

from expense.constants import DEFAULT_SCAN_SCHEDULE, WORKFLOW_KEY
from expense.models import ExpenseAppConfig, ExpenseUserConfig
from expense.services.config_service import (
    get_app_config,
    get_user_config,
    set_user_enabled,
)


pytestmark = [pytest.mark.unit, pytest.mark.django_db]


class TestAppConfig:
    def test_first_access_creates_defaults(self):
        config = get_app_config()

        assert config.workflow_key == WORKFLOW_KEY
        assert config.scan_schedule == DEFAULT_SCAN_SCHEDULE
        assert config.is_active is True

    def test_access_is_idempotent(self):
        first = get_app_config()
        second = get_app_config()

        assert first.pk == second.pk
        assert ExpenseAppConfig.objects.count() == 1


class TestUserConfig:
    def test_first_access_creates_disabled_row(self, user):
        config = get_user_config(user)

        assert config.enabled is False
        assert config.enabled_at is None
        assert ExpenseUserConfig.objects.count() == 1

    def test_enabling_stamps_the_scan_floor(self, user):
        config = set_user_enabled(get_user_config(user), True)

        assert config.enabled is True
        assert config.enabled_at is not None

    def test_disabling_keeps_the_original_floor(self, user):
        config = set_user_enabled(get_user_config(user), True)
        first_enabled_at = config.enabled_at

        config = set_user_enabled(config, False)

        assert config.enabled is False
        assert config.enabled_at == first_enabled_at

    def test_re_enabling_moves_the_floor_forward(self, user):
        config = set_user_enabled(get_user_config(user), True)
        first_enabled_at = config.enabled_at
        config = set_user_enabled(config, False)

        config = set_user_enabled(config, True)

        # A fresh switch-on must not reach back into mail that arrived while
        # the app was off, otherwise re-enabling would silently spend credits
        # on a whole mailbox history.
        assert config.enabled_at > first_enabled_at

    def test_enabling_twice_does_not_move_the_floor(self, user):
        config = set_user_enabled(get_user_config(user), True)
        first_enabled_at = config.enabled_at

        config = set_user_enabled(config, True)

        assert config.enabled_at == first_enabled_at

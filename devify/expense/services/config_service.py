"""Configuration access helpers for the Expense app."""

from __future__ import annotations

from django.utils import timezone

from expense.constants import WORKFLOW_KEY
from expense.models import ExpenseAppConfig, ExpenseUserConfig


def get_app_config() -> ExpenseAppConfig:
    """Return the platform-level config, creating defaults on first use."""
    config, _ = ExpenseAppConfig.objects.get_or_create(
        workflow_key=WORKFLOW_KEY
    )
    return config


def get_user_config(user) -> ExpenseUserConfig:
    """Return the per-user config, creating a disabled row on first use."""
    config, _ = ExpenseUserConfig.objects.get_or_create(user=user)
    return config


def set_user_enabled(
    config: ExpenseUserConfig, enabled: bool
) -> ExpenseUserConfig:
    """
    Flip the user switch.

    ``enabled_at`` is the scan floor: turning the app on never reaches back
    into mail that arrived earlier, so a fresh switch-on cannot silently
    consume credits on a full mailbox history.
    """
    if enabled and not config.enabled:
        config.enabled = True
        config.enabled_at = timezone.now()
        config.save(update_fields=["enabled", "enabled_at", "updated_at"])
    elif not enabled and config.enabled:
        config.enabled = False
        config.save(update_fields=["enabled", "updated_at"])
    return config

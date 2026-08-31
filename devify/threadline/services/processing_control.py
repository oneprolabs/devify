"""
A per-user brake on email processing.

Fetching and processing are separate concerns: mail keeps arriving, but a
user who has just connected a mailbox with years of history needs a way to
stop the workflow chewing through it before they have tuned their filters.

Paused mail stays in FETCHED and is picked up normally once the brake is
released.
"""

from __future__ import annotations

import logging

from threadline.models import Settings

logger = logging.getLogger(__name__)

EMAIL_CONFIG_KEY = "email_config"
PAUSE_FIELD = "processing_paused"


def is_processing_paused(user_id: int) -> bool:
    setting = Settings.objects.filter(
        user_id=user_id, key=EMAIL_CONFIG_KEY, is_active=True
    ).first()
    if not setting:
        return False
    return bool((setting.value or {}).get(PAUSE_FIELD))


def paused_user_ids() -> set[int]:
    """
    Every user currently holding the brake.

    Read in one query so batch jobs can exclude them without asking per
    email.
    """
    rows = Settings.objects.filter(
        key=EMAIL_CONFIG_KEY, is_active=True
    ).values_list("user_id", "value")
    return {
        user_id
        for user_id, value in rows
        if isinstance(value, dict) and value.get(PAUSE_FIELD)
    }


def set_processing_paused(user, paused: bool) -> bool:
    setting, _ = Settings.objects.get_or_create(
        user=user,
        key=EMAIL_CONFIG_KEY,
        defaults={"value": {}, "is_active": True},
    )
    value = dict(setting.value or {})
    value[PAUSE_FIELD] = bool(paused)
    setting.value = value
    setting.save(update_fields=["value", "updated_at"])
    logger.info(
        "Email processing %s for user %s",
        "paused" if paused else "resumed",
        user.id,
    )
    return bool(paused)

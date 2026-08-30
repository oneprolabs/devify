"""Shared pytest fixtures for Expense tests."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import django
import pytest
from dotenv import load_dotenv


project_root = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(project_root))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

env_file = os.getenv("DEVIFY_ENV_FILE")
if env_file:
    candidate = Path(env_file).expanduser()
    if not candidate.is_absolute():
        candidate = project_root / candidate
    if candidate.exists():
        load_dotenv(candidate, override=False)
else:
    default_env_file = project_root / ".env.test"
    if default_env_file.exists():
        load_dotenv(default_env_file, override=False)

django.setup()

from django.contrib.auth import get_user_model  # noqa: E402
from rest_framework.test import APIClient  # noqa: E402


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user(db):
    return get_user_model().objects.create_user(
        username="expense_user",
        email="expense_user@example.com",
        password="test-password",
    )


@pytest.fixture
def other_user(db):
    return get_user_model().objects.create_user(
        username="expense_other",
        email="expense_other@example.com",
        password="test-password",
    )


@pytest.fixture
def admin_user(db):
    return get_user_model().objects.create_superuser(
        username="expense_admin",
        email="expense_admin@example.com",
        password="test-password",
    )

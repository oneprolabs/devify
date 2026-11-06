"""
Main pytest configuration for Billing tests

This module provides shared pytest fixtures and configuration for all
billing test categories (unit, integration tests).
"""

import os
import sys
import django
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(project_root))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
os.environ.setdefault('CELERY_TASK_ALWAYS_EAGER', 'true')

django.setup()

import pytest

from .fixtures.conftest import *
from .fixtures.factories import *


@pytest.fixture(autouse=True)
def eager_celery_tasks(settings):
    """Run queued Celery work inline so audit rows exist during the test.

    The environment variable above is only read while Django loads settings,
    which pytest-django has usually done already. Overriding the setting per
    test is what actually makes ``queue_billing_audit_event`` write the row
    instead of handing it to a broker.
    """

    settings.CELERY_TASK_ALWAYS_EAGER = True
    settings.CELERY_TASK_EAGER_PROPAGATES = True

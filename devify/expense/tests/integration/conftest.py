"""Run expense integration tests against the existing dev database."""

import pytest


@pytest.fixture(scope="session")
def django_db_setup():
    """Reuse the provided database without creating a test database."""
    yield

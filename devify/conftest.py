"""Project-wide pytest fixtures.

Tests must not share the cache with a running dev stack. Task locks,
scheduler guards and rate limits all live in ``django.core.cache``; when the
cache is Redis and the dev scheduler is running, unrelated tests read a lock
another process holds and fail at random. Every test therefore gets a private
in-memory cache unless it installs its own via ``override_settings``.
"""

import pytest
from django.core.cache import cache

LOCMEM_CACHE = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "devify-tests",
    }
}


@pytest.fixture(autouse=True)
def isolated_cache(settings):
    # LocMemCache keeps one store per LOCATION, so tests would still see each
    # other's keys; clear on both sides of every test.
    settings.CACHES = LOCMEM_CACHE
    cache.clear()
    yield
    cache.clear()

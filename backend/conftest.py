"""Top-level pytest config — makes `backend/` importable + forces the
in-memory channel layer for tests so they don't depend on Redis."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))


def pytest_configure(config):
    # Force the in-memory channel layer for tests. Must run BEFORE Django/channels
    # consumers attempt to resolve the layer.
    from django.conf import settings
    if settings.configured:
        settings.CHANNEL_LAYERS = {
            "default": {"BACKEND": "channels.layers.InMemoryChannelLayer"},
        }
        # Phase 5: override Redis cache with locmem so tests don't require a
        # reachable Redis instance. Throttle counters use this cache too, so
        # throttling remains active (needed for Task 6 login-throttle tests).
        settings.CACHES = {
            "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}
        }


@pytest.fixture(autouse=True)
def _clear_cache_between_tests():
    """Cache state (throttle buckets, cached views) leaks across tests in the
    same process. Clear it before every test so the global anon-rate throttle
    (30/min) doesn't accumulate counts and produce 429s in tests that hit
    anonymous endpoints later in the run."""
    from django.core.cache import cache
    cache.clear()
    yield

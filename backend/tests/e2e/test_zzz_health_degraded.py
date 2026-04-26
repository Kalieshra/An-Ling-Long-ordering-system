"""E2E: /healthz/ returns 503 when Redis is unreachable.

This test STOPS the redis container temporarily, then restarts it. The `zzz_`
prefix puts it LAST in pytest's alphabetical ordering so it doesn't disrupt
other E2E tests. Wrapped in try/finally so redis is always brought back up.
"""
import shutil
import subprocess
import time

import pytest
import requests

pytestmark = pytest.mark.e2e


def _compose(*args):
    if shutil.which("docker") is None:
        pytest.skip("docker CLI not on PATH")
    return subprocess.run(
        ["docker", "compose", *args],
        check=False, capture_output=True, text=True, timeout=30,
    )


class TestHealthDegraded:
    def test_healthz_returns_503_when_redis_down(self, base_url):
        # Sanity: healthz is currently 200
        r = requests.get(f"{base_url}/healthz/", timeout=5)
        assert r.status_code == 200, r.text

        try:
            # Stop redis
            _compose("stop", "redis")
            time.sleep(2)

            # /healthz/ should now report degraded with 503
            r = requests.get(f"{base_url}/healthz/", timeout=5)
            assert r.status_code == 503, r.text
            body = r.json()
            assert body["status"] == "degraded"
            assert body["checks"]["cache"]["ok"] is False
        finally:
            # Always bring redis back even if asserts failed
            _compose("start", "redis")
            # Wait for redis to be healthy again so subsequent test runs work
            for _ in range(30):
                try:
                    r = requests.get(f"{base_url}/healthz/", timeout=3)
                    if r.status_code == 200:
                        break
                except requests.RequestException:
                    pass
                time.sleep(1)

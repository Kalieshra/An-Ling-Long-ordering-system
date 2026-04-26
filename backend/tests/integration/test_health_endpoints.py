"""Integration tests for /healthz/ and /readyz/."""
from unittest.mock import patch

import pytest
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db


class TestHealthz:
    def test_healthz_returns_200_with_checks(self):
        c = APIClient()
        resp = c.get("/healthz/")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["checks"]["db"]["ok"] is True
        assert body["checks"]["cache"]["ok"] is True

    def test_healthz_returns_503_when_db_down(self):
        c = APIClient()
        with patch("rms.health._check_db") as mock_db:
            from rms.health import HealthStatus
            mock_db.return_value = HealthStatus(False, "db connect failed")
            resp = c.get("/healthz/")
        assert resp.status_code == 503
        body = resp.json()
        assert body["status"] == "degraded"
        assert body["checks"]["db"]["ok"] is False

    def test_healthz_returns_503_when_cache_down(self):
        c = APIClient()
        with patch("rms.health._check_cache") as mock_cache:
            from rms.health import HealthStatus
            mock_cache.return_value = HealthStatus(False, "redis unreachable")
            resp = c.get("/healthz/")
        assert resp.status_code == 503

    def test_healthz_anonymous_access(self):
        c = APIClient()
        resp = c.get("/healthz/")
        # No 401/403 — health endpoints must be unauthenticated.
        assert resp.status_code in (200, 503)


class TestReadyz:
    def test_readyz_returns_200(self):
        c = APIClient()
        resp = c.get("/readyz/")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

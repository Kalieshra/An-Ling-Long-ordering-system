"""Unit tests for the health check helpers — mocked DB / cache failures."""
from unittest.mock import patch

import pytest
from rms.health import _check_cache, _check_db

pytestmark = pytest.mark.django_db


class TestCheckDb:
    def test_passes_when_db_reachable(self):
        result = _check_db()
        assert result.ok is True
        assert result.detail.startswith("ok")

    def test_fails_with_detail_when_db_raises(self):
        with patch("rms.health.connection") as mock_conn:
            mock_conn.cursor.side_effect = RuntimeError("db down")
            result = _check_db()
        assert result.ok is False
        assert "db down" in result.detail


class TestCheckCache:
    def test_passes_when_cache_roundtrips(self):
        result = _check_cache()
        assert result.ok is True

    def test_fails_when_cache_raises(self):
        with patch("rms.health.cache") as mock_cache:
            mock_cache.set.side_effect = RuntimeError("redis unreachable")
            result = _check_cache()
        assert result.ok is False
        assert "redis unreachable" in result.detail

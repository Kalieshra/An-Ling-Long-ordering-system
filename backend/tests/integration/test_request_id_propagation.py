"""Integration test: X-Request-ID surfaces in responses through the full stack."""
import pytest
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db


class TestRequestIdPropagation:
    def test_response_has_request_id_header(self):
        c = APIClient()
        resp = c.get("/api/v1/menu/categories/")
        assert resp.status_code == 200
        assert "X-Request-ID" in resp
        assert len(resp["X-Request-ID"]) >= 8

    def test_inbound_request_id_is_echoed(self):
        c = APIClient()
        resp = c.get("/api/v1/menu/categories/", HTTP_X_REQUEST_ID="caller-rid-1")
        assert resp["X-Request-ID"] == "caller-rid-1"

    def test_pathological_inbound_id_replaced(self):
        c = APIClient()
        resp = c.get("/api/v1/menu/categories/", HTTP_X_REQUEST_ID="x" * 2048)
        assert resp["X-Request-ID"] != "x" * 2048
        assert len(resp["X-Request-ID"]) <= 64

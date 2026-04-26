"""Integration tests for the OpenAPI schema endpoints."""
import pytest
import yaml
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db


class TestOpenAPISchema:
    def test_schema_endpoint_serves_yaml(self):
        c = APIClient()
        resp = c.get("/api/schema/")
        assert resp.status_code == 200
        assert "openapi" in resp.content.decode()[:500].lower()

    def test_schema_yaml_parses(self):
        c = APIClient()
        resp = c.get("/api/schema/")
        doc = yaml.safe_load(resp.content)
        assert doc["openapi"].startswith("3.")
        assert "paths" in doc
        # Sanity checks: our key endpoints are listed
        paths = list(doc["paths"].keys())
        assert any(p.endswith("/api/v1/menu/categories/") for p in paths)
        assert any(p.endswith("/api/v1/orders/") for p in paths)
        assert any(p.endswith("/api/v1/me/") for p in paths)

    def test_swagger_ui_renders(self):
        c = APIClient()
        resp = c.get("/api/schema/swagger-ui/")
        assert resp.status_code == 200
        assert b"swagger" in resp.content.lower() or b"SwaggerUI" in resp.content

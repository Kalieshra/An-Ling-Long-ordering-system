"""CORS allow-list integration tests.

The `CORS_ALLOWED_ORIGINS` setting is read from the env var of the same name,
which defaults to `[]`. We override it via `@override_settings` to test both
allowed and blocked origins.
"""
import pytest
from django.test import Client, TestCase, override_settings

pytestmark = pytest.mark.django_db


@override_settings(CORS_ALLOWED_ORIGINS=["http://app.example.com"])
class TestCORSAllowList(TestCase):
    def test_allowed_origin_preflight(self):
        c = Client()
        resp = c.options(
            "/api/v1/menu/categories/",
            HTTP_ORIGIN="http://app.example.com",
            HTTP_ACCESS_CONTROL_REQUEST_METHOD="GET",
        )
        assert resp.status_code == 200
        assert resp["Access-Control-Allow-Origin"] == "http://app.example.com"

    def test_disallowed_origin_no_cors_header(self):
        c = Client()
        resp = c.options(
            "/api/v1/menu/categories/",
            HTTP_ORIGIN="http://evil.example.com",
            HTTP_ACCESS_CONTROL_REQUEST_METHOD="GET",
        )
        # corsheaders does NOT add the Access-Control-Allow-Origin header for
        # disallowed origins. The browser will block the preflight client-side.
        assert "Access-Control-Allow-Origin" not in resp


class TestCORSDefaultEmpty(TestCase):
    def test_with_no_allow_list_no_cors_header(self):
        # CORS_ALLOWED_ORIGINS defaults to [] in test settings.
        c = Client()
        resp = c.options(
            "/api/v1/menu/categories/",
            HTTP_ORIGIN="http://app.example.com",
            HTTP_ACCESS_CONTROL_REQUEST_METHOD="GET",
        )
        assert "Access-Control-Allow-Origin" not in resp

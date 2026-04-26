"""Integration tests for login throttling — 5/min cap on /api/v1/auth/login/."""
import pytest
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db


@pytest.fixture
def customer(django_user_model):
    return django_user_model.objects.create_user(
        email="alice@x.com", password="alice-pw-long-enough", role="customer",
    )


class TestLoginThrottling:
    URL = "/api/v1/auth/login/"

    def test_5_in_a_row_OK_then_6th_429(self, customer):
        c = APIClient()
        # 5 attempts (failed credentials are fine — throttle counts attempts, not successes).
        for i in range(5):
            resp = c.post(self.URL, {"email": "alice@x.com", "password": "wrong"}, format="json")
            assert resp.status_code in (200, 401), f"attempt {i+1}: {resp.status_code}"
        # 6th: 429
        resp = c.post(self.URL, {"email": "alice@x.com", "password": "wrong"}, format="json")
        assert resp.status_code == 429

    def test_unrelated_endpoint_unaffected(self, customer):
        # Hammer login then verify menu/categories/ still works (separate throttle scope).
        c = APIClient()
        for _ in range(6):
            c.post(self.URL, {"email": "alice@x.com", "password": "wrong"}, format="json")
        resp = c.get("/api/v1/menu/categories/")
        assert resp.status_code == 200

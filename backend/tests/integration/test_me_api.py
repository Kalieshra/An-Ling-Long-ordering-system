"""Integration tests for /api/v1/me/."""
import pytest
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db


@pytest.fixture
def customer(django_user_model):
    return django_user_model.objects.create_user(
        email="alice@x.com", password="alice-pw-long-enough", role="customer",
        first_name="Alice", last_name="Anderson", phone="010",
    )


def _jwt_login(client, email, password):
    resp = client.post("/api/v1/auth/login/", {"email": email, "password": password}, format="json")
    assert resp.status_code == 200, resp.data
    return resp.data["access"]


@pytest.fixture
def auth_client(customer):
    c = APIClient()
    token = _jwt_login(c, "alice@x.com", "alice-pw-long-enough")
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return c


class TestMeProfile:
    def test_get_returns_my_profile(self, auth_client, customer):
        resp = auth_client.get("/api/v1/me/")
        assert resp.status_code == 200
        assert resp.data["email"] == "alice@x.com"
        assert resp.data["first_name"] == "Alice"
        assert resp.data["role"] == "customer"

    def test_patch_updates_first_last_phone(self, auth_client, customer):
        resp = auth_client.patch(
            "/api/v1/me/",
            {"first_name": "Alicia", "phone": "020"},
            format="json",
        )
        assert resp.status_code == 200
        assert resp.data["first_name"] == "Alicia"
        assert resp.data["phone"] == "020"
        customer.refresh_from_db()
        assert customer.first_name == "Alicia"
        assert customer.phone == "020"

    def test_patch_email_is_read_only(self, auth_client, customer):
        resp = auth_client.patch(
            "/api/v1/me/",
            {"email": "hacked@x.com"},
            format="json",
        )
        assert resp.status_code == 200
        customer.refresh_from_db()
        assert customer.email == "alice@x.com"

    def test_patch_role_is_read_only(self, auth_client, customer):
        resp = auth_client.patch(
            "/api/v1/me/",
            {"role": "admin"},
            format="json",
        )
        assert resp.status_code == 200
        customer.refresh_from_db()
        assert customer.role == "customer"

    def test_anonymous_401(self):
        c = APIClient()
        resp = c.get("/api/v1/me/")
        assert resp.status_code == 401

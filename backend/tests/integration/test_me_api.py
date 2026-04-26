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


class TestMeAddresses:
    URL = "/api/v1/me/addresses/"

    def test_list_initially_empty(self, auth_client):
        resp = auth_client.get(self.URL)
        assert resp.status_code == 200
        # Pagination is disabled for this list (small data) — accept either flat list or paginated shape.
        data = resp.data
        if isinstance(data, dict):
            data = data["results"]
        assert data == []

    def test_create_address(self, auth_client):
        body = {
            "label": "Home",
            "line1": "10 Cairo St",
            "city": "Zagazig",
            "phone": "0100-1",
            "is_default": True,
        }
        resp = auth_client.post(self.URL, body, format="json")
        assert resp.status_code == 201, resp.data
        assert resp.data["label"] == "Home"
        assert resp.data["is_default"] is True

    def test_list_returns_only_my_addresses(self, auth_client, customer, django_user_model):
        from accounts.models import SavedAddress
        SavedAddress.objects.create(
            user=customer, label="Mine", line1="A", city="Z", phone="0",
        )
        other = django_user_model.objects.create_user(
            email="bob@x.com", password="bob-pw-long-enough", role="customer",
        )
        SavedAddress.objects.create(
            user=other, label="Theirs", line1="B", city="Z", phone="0",
        )
        resp = auth_client.get(self.URL)
        rows = resp.data if isinstance(resp.data, list) else resp.data["results"]
        labels = [a["label"] for a in rows]
        assert "Mine" in labels
        assert "Theirs" not in labels

    def test_update_my_address(self, auth_client, customer):
        from accounts.models import SavedAddress
        a = SavedAddress.objects.create(user=customer, label="Home", line1="A", city="Z", phone="0")
        resp = auth_client.patch(f"{self.URL}{a.id}/", {"label": "Renamed"}, format="json")
        assert resp.status_code == 200
        a.refresh_from_db()
        assert a.label == "Renamed"

    def test_delete_my_address(self, auth_client, customer):
        from accounts.models import SavedAddress
        a = SavedAddress.objects.create(user=customer, label="Home", line1="A", city="Z", phone="0")
        resp = auth_client.delete(f"{self.URL}{a.id}/")
        assert resp.status_code == 204
        assert not SavedAddress.objects.filter(pk=a.id).exists()

    def test_cannot_access_others_address(self, auth_client, django_user_model):
        from accounts.models import SavedAddress
        other = django_user_model.objects.create_user(
            email="bob@x.com", password="bob-pw-long-enough", role="customer",
        )
        a = SavedAddress.objects.create(user=other, label="Other", line1="A", city="Z", phone="0")
        resp = auth_client.get(f"{self.URL}{a.id}/")
        assert resp.status_code == 404

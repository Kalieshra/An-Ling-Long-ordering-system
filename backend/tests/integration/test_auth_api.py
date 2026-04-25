"""Integration tests for JWT auth endpoints (customer-facing)."""
import pytest
from accounts.models import Role, User
from rest_framework.test import APIClient


@pytest.fixture
def client():
    return APIClient()


@pytest.mark.django_db
class TestRegister:
    url = "/api/v1/auth/register/"

    def test_registers_customer_with_valid_payload(self, client):
        resp = client.post(
            self.url,
            {
                "email": "new@example.com",
                "password": "s3cret-pw-long",
                "name": "New User",
                "phone": "+201001234567",
            },
            format="json",
        )
        assert resp.status_code == 201
        assert "access" in resp.data
        assert "refresh" in resp.data
        assert resp.data["user"]["email"] == "new@example.com"
        assert resp.data["user"]["role"] == "customer"

        user = User.objects.get(email="new@example.com")
        assert user.role == Role.CUSTOMER
        assert user.first_name == "New User"

    def test_rejects_weak_password(self, client):
        resp = client.post(
            self.url,
            {"email": "x@example.com", "password": "short", "name": "X"},
            format="json",
        )
        assert resp.status_code == 400
        assert "password" in resp.data

    def test_rejects_duplicate_email(self, client):
        User.objects.create_user(email="dup@example.com", password="s3cret-pw-long")
        resp = client.post(
            self.url,
            {"email": "dup@example.com", "password": "s3cret-pw-long", "name": "Dup"},
            format="json",
        )
        assert resp.status_code == 400

    def test_rejects_duplicate_email_case_insensitive(self, client):
        User.objects.create_user(email="dup@example.com", password="s3cret-pw-long")
        resp = client.post(
            self.url,
            {"email": "DUP@Example.COM", "password": "s3cret-pw-long", "name": "Dup2"},
            format="json",
        )
        assert resp.status_code == 400

    def test_registration_always_creates_customer_role(self, client):
        """Even if payload tries to set role=admin, user must be created as customer."""
        resp = client.post(
            self.url,
            {
                "email": "sneaky@example.com",
                "password": "s3cret-pw-long",
                "name": "Sneaky",
                "role": "admin",
            },
            format="json",
        )
        assert resp.status_code == 201
        user = User.objects.get(email="sneaky@example.com")
        assert user.role == Role.CUSTOMER


@pytest.mark.django_db
class TestLogin:
    url = "/api/v1/auth/login/"

    def test_returns_access_and_refresh_on_valid_credentials(self, client):
        User.objects.create_user(
            email="login@example.com", password="s3cret-pw-long", role=Role.CUSTOMER
        )
        resp = client.post(
            self.url,
            {"email": "login@example.com", "password": "s3cret-pw-long"},
            format="json",
        )
        assert resp.status_code == 200
        assert "access" in resp.data
        assert "refresh" in resp.data
        assert resp.data["user"]["email"] == "login@example.com"

    def test_rejects_bad_password(self, client):
        User.objects.create_user(email="login@example.com", password="s3cret-pw-long")
        resp = client.post(
            self.url, {"email": "login@example.com", "password": "wrong"}, format="json"
        )
        assert resp.status_code == 401

    def test_rejects_unknown_email(self, client):
        resp = client.post(
            self.url, {"email": "nobody@example.com", "password": "s3cret-pw-long"}, format="json"
        )
        assert resp.status_code == 401

    def test_login_is_case_insensitive_on_email(self, client):
        User.objects.create_user(email="alice@example.com", password="s3cret-pw-long")
        resp = client.post(
            self.url,
            {"email": "Alice@EXAMPLE.COM", "password": "s3cret-pw-long"},
            format="json",
        )
        assert resp.status_code == 200
        assert "access" in resp.data


@pytest.mark.django_db
class TestRefresh:
    url = "/api/v1/auth/refresh/"

    def _login(self, client):
        User.objects.create_user(email="r@example.com", password="s3cret-pw-long")
        resp = client.post(
            "/api/v1/auth/login/",
            {"email": "r@example.com", "password": "s3cret-pw-long"},
            format="json",
        )
        return resp.data["refresh"], resp.data["access"]

    def test_refresh_rotates_tokens(self, client):
        refresh, _access = self._login(client)
        resp = client.post(self.url, {"refresh": refresh}, format="json")
        assert resp.status_code == 200
        assert "access" in resp.data
        assert "refresh" in resp.data
        assert resp.data["refresh"] != refresh

    def test_old_refresh_blacklisted_after_rotation(self, client):
        refresh, _access = self._login(client)
        first = client.post(self.url, {"refresh": refresh}, format="json")
        assert first.status_code == 200
        second = client.post(self.url, {"refresh": refresh}, format="json")
        assert second.status_code == 401


@pytest.mark.django_db
class TestLogout:
    url = "/api/v1/auth/logout/"

    def _login(self, client):
        User.objects.create_user(email="o@example.com", password="s3cret-pw-long")
        resp = client.post(
            "/api/v1/auth/login/",
            {"email": "o@example.com", "password": "s3cret-pw-long"},
            format="json",
        )
        return resp.data["refresh"], resp.data["access"]

    def test_logout_blacklists_refresh(self, client):
        refresh, access = self._login(client)
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        resp = client.post(self.url, {"refresh": refresh}, format="json")
        assert resp.status_code == 205
        resp2 = client.post("/api/v1/auth/refresh/", {"refresh": refresh}, format="json")
        assert resp2.status_code == 401

    def test_logout_requires_auth(self, client):
        resp = client.post(self.url, {"refresh": "whatever"}, format="json")
        assert resp.status_code == 401


@pytest.mark.django_db
class TestPasswordChange:
    url = "/api/v1/auth/password/change/"

    def test_changes_password(self, client):
        user = User.objects.create_user(email="p@example.com", password="old-pw-long-enough")
        login = client.post(
            "/api/v1/auth/login/",
            {"email": "p@example.com", "password": "old-pw-long-enough"},
            format="json",
        )
        access = login.data["access"]
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        resp = client.post(
            self.url,
            {"old_password": "old-pw-long-enough", "new_password": "new-pw-long-enough"},
            format="json",
        )
        assert resp.status_code == 200
        user.refresh_from_db()
        assert user.check_password("new-pw-long-enough")

    def test_rejects_wrong_old_password(self, client):
        User.objects.create_user(email="p@example.com", password="old-pw-long-enough")
        login = client.post(
            "/api/v1/auth/login/",
            {"email": "p@example.com", "password": "old-pw-long-enough"},
            format="json",
        )
        access = login.data["access"]
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        resp = client.post(
            self.url,
            {"old_password": "wrong", "new_password": "new-pw-long-enough"},
            format="json",
        )
        assert resp.status_code == 400

"""Integration tests for staff login + role-based redirect + role-gated dashboards."""
import pytest
from accounts.models import Role, User
from django.test import Client


@pytest.fixture
def client():
    return Client()


@pytest.mark.django_db
class TestStaffLogin:
    def _make(self, role, email="s@example.com"):
        return User.objects.create_user(email=email, password="pw-long-enough", role=role)

    def test_get_login_renders(self, client):
        resp = client.get("/login/")
        assert resp.status_code == 200
        # Be lenient about exact wording; just ensure form is on the page
        assert b"email" in resp.content.lower() or b"Email" in resp.content
        assert b"password" in resp.content.lower() or b"Password" in resp.content

    def test_admin_login_redirects_to_dashboard(self, client):
        self._make(Role.ADMIN)
        resp = client.post(
            "/login/", {"email": "s@example.com", "password": "pw-long-enough"}
        )
        assert resp.status_code == 302
        assert resp["Location"].endswith("/dashboard/")

    def test_cashier_login_redirects_to_cashier(self, client):
        self._make(Role.CASHIER)
        resp = client.post(
            "/login/", {"email": "s@example.com", "password": "pw-long-enough"}
        )
        assert resp.status_code == 302
        assert resp["Location"].endswith("/cashier/")

    def test_kitchen_login_redirects_to_kitchen(self, client):
        self._make(Role.KITCHEN)
        resp = client.post(
            "/login/", {"email": "s@example.com", "password": "pw-long-enough"}
        )
        assert resp.status_code == 302
        assert resp["Location"].endswith("/kitchen/")

    def test_customer_cannot_use_staff_login(self, client):
        self._make(Role.CUSTOMER)
        resp = client.post(
            "/login/", {"email": "s@example.com", "password": "pw-long-enough"}
        )
        # Form re-rendered with error; no session established
        assert resp.status_code in (200, 403)
        assert "_auth_user_id" not in client.session

    def test_logout_clears_session(self, client):
        user = self._make(Role.ADMIN)
        client.force_login(user)
        resp = client.post("/logout/")
        assert resp.status_code == 302
        assert "_auth_user_id" not in client.session

    def test_dashboard_requires_admin(self, client):
        self._make(Role.CASHIER, email="c@example.com")
        # NB: client.login uses USERNAME_FIELD; email here.
        client.login(email="c@example.com", password="pw-long-enough")
        resp = client.get("/dashboard/")
        assert resp.status_code == 403

    def test_cashier_page_renders_for_cashier(self, client):
        user = self._make(Role.CASHIER)
        client.force_login(user)
        resp = client.get("/cashier/")
        assert resp.status_code == 200
        assert b"Cashier" in resp.content

    def test_kitchen_page_renders_for_kitchen(self, client):
        user = self._make(Role.KITCHEN)
        client.force_login(user)
        resp = client.get("/kitchen/")
        assert resp.status_code == 200

    def test_admin_page_renders_for_admin(self, client):
        user = self._make(Role.ADMIN)
        client.force_login(user)
        resp = client.get("/dashboard/")
        assert resp.status_code == 200
        assert b"Admin" in resp.content or b"Dashboard" in resp.content

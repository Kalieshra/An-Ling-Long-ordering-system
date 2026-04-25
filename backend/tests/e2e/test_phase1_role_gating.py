"""Phase 1 E2E: role-gated auth.

Covers spec §6 Phase 1 E2E criteria:
1. Admin lands on /dashboard/; 403 on /cashier/ and /kitchen/
2. Cashier lands on /cashier/; 403 on /dashboard/ and /kitchen/
3. Kitchen lands on /kitchen/; 403 on /cashier/ and /dashboard/
4. Customer JWT cannot reach staff dashboards (auth ignored on session-only routes)
5. JWT refresh rotates; logout blacklists
"""
import pytest
import requests
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.e2e


def _login_ui(page: Page, base_url: str, email: str, password: str) -> None:
    page.goto(f"{base_url}/login/")
    page.fill("input[name='email']", email)
    page.fill("input[name='password']", password)
    page.click("button[type='submit']")


class TestAdminGating:
    def test_admin_lands_on_dashboard(self, page: Page, base_url, users):
        _login_ui(page, base_url, users["admin"]["email"], users["admin"]["password"])
        expect(page).to_have_url(f"{base_url}/dashboard/")
        expect(page.get_by_text("Admin Dashboard")).to_be_visible()

    def test_admin_cannot_open_cashier(self, page: Page, base_url, users):
        _login_ui(page, base_url, users["admin"]["email"], users["admin"]["password"])
        resp = page.goto(f"{base_url}/cashier/")
        assert resp.status == 403

    def test_admin_cannot_open_kitchen(self, page: Page, base_url, users):
        _login_ui(page, base_url, users["admin"]["email"], users["admin"]["password"])
        resp = page.goto(f"{base_url}/kitchen/")
        assert resp.status == 403


class TestCashierGating:
    def test_cashier_lands_on_cashier(self, page: Page, base_url, users):
        _login_ui(page, base_url, users["cashier"]["email"], users["cashier"]["password"])
        expect(page).to_have_url(f"{base_url}/cashier/")
        expect(page.get_by_text("Cashier POS")).to_be_visible()

    def test_cashier_cannot_open_dashboard(self, page: Page, base_url, users):
        _login_ui(page, base_url, users["cashier"]["email"], users["cashier"]["password"])
        resp = page.goto(f"{base_url}/dashboard/")
        assert resp.status == 403

    def test_cashier_cannot_open_kitchen(self, page: Page, base_url, users):
        _login_ui(page, base_url, users["cashier"]["email"], users["cashier"]["password"])
        resp = page.goto(f"{base_url}/kitchen/")
        assert resp.status == 403


class TestKitchenGating:
    def test_kitchen_lands_on_kitchen(self, page: Page, base_url, users):
        _login_ui(page, base_url, users["kitchen"]["email"], users["kitchen"]["password"])
        expect(page).to_have_url(f"{base_url}/kitchen/")
        expect(page.get_by_text("Kitchen Display")).to_be_visible()

    def test_kitchen_cannot_open_cashier(self, page: Page, base_url, users):
        _login_ui(page, base_url, users["kitchen"]["email"], users["kitchen"]["password"])
        resp = page.goto(f"{base_url}/cashier/")
        assert resp.status == 403

    def test_kitchen_cannot_open_dashboard(self, page: Page, base_url, users):
        _login_ui(page, base_url, users["kitchen"]["email"], users["kitchen"]["password"])
        resp = page.goto(f"{base_url}/dashboard/")
        assert resp.status == 403


class TestCustomerJwtCannotReachStaff:
    def test_customer_jwt_does_not_grant_dashboard(self, base_url, users):
        resp = requests.post(
            f"{base_url}/api/v1/auth/login/",
            json={"email": users["customer"]["email"], "password": users["customer"]["password"]},
            timeout=5,
        )
        assert resp.status_code == 200
        access = resp.json()["access"]

        dash = requests.get(
            f"{base_url}/dashboard/",
            headers={"Authorization": f"Bearer {access}"},
            allow_redirects=False,
            timeout=5,
        )
        # Either redirect-to-login or forbidden — both deny access.
        assert dash.status_code in (302, 403)
        if dash.status_code == 302:
            assert "/login/" in dash.headers.get("Location", "")

    def test_customer_cannot_login_via_staff_form(self, page: Page, base_url, users):
        _login_ui(page, base_url, users["customer"]["email"], users["customer"]["password"])
        expect(page).to_have_url(f"{base_url}/login/")
        expect(page.get_by_text("Customer accounts cannot sign in here.")).to_be_visible()


class TestJwtRotationAndBlacklist:
    def test_refresh_rotates_and_old_is_blacklisted(self, base_url, users):
        login = requests.post(
            f"{base_url}/api/v1/auth/login/",
            json={"email": users["customer"]["email"], "password": users["customer"]["password"]},
            timeout=5,
        )
        refresh = login.json()["refresh"]
        first = requests.post(
            f"{base_url}/api/v1/auth/refresh/", json={"refresh": refresh}, timeout=5
        )
        assert first.status_code == 200
        assert first.json()["refresh"] != refresh
        second = requests.post(
            f"{base_url}/api/v1/auth/refresh/", json={"refresh": refresh}, timeout=5
        )
        assert second.status_code == 401

    def test_logout_blacklists_refresh(self, base_url, users):
        login = requests.post(
            f"{base_url}/api/v1/auth/login/",
            json={"email": users["customer"]["email"], "password": users["customer"]["password"]},
            timeout=5,
        )
        access = login.json()["access"]
        refresh = login.json()["refresh"]
        out = requests.post(
            f"{base_url}/api/v1/auth/logout/",
            json={"refresh": refresh},
            headers={"Authorization": f"Bearer {access}"},
            timeout=5,
        )
        assert out.status_code == 205
        again = requests.post(
            f"{base_url}/api/v1/auth/refresh/", json={"refresh": refresh}, timeout=5
        )
        assert again.status_code == 401

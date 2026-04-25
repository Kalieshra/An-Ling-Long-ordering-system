"""Phase 2 E2E: admin manages menu, customer API reflects changes.

Pre-reqs (handled by tests/e2e/conftest.py from Phase 1):
- docker compose stack running on localhost:18000
- Seed users for admin/cashier/kitchen/customer already in DB
"""
import io
import shutil
import subprocess

import pytest
import requests
from PIL import Image
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.e2e


def _png_bytes(size=(50, 50)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color="orange").save(buf, format="PNG")
    return buf.getvalue()


def _login_admin(page: Page, base_url: str, users):
    page.goto(f"{base_url}/login/")
    page.fill("input[name='email']", users["admin"]["email"])
    page.fill("input[name='password']", users["admin"]["password"])
    page.click("button[type='submit']")
    expect(page).to_have_url(f"{base_url}/dashboard/")


def _submit_form(page: Page) -> None:
    """Click the primary Save button (not the Logout button in the navbar)."""
    page.locator("button.btn-primary[type='submit']").click()


def _cleanup_e2e_menu_data() -> None:
    """Delete any leftover E2E categories/items from previous runs."""
    if shutil.which("docker") is None:
        return
    script = (
        "from menu.models import Category, MenuItem\n"
        "MenuItem.objects.filter(name__startswith='E2E ').delete()\n"
        "Category.objects.filter(slug__startswith='e2e-').delete()\n"
        "print('cleaned')\n"
    )
    subprocess.run(
        ["docker", "compose", "exec", "-T", "web", "python", "manage.py", "shell", "-c", script],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )


@pytest.fixture(scope="session", autouse=True)
def cleanup_e2e_data():
    """Wipe E2E menu fixtures before this module's tests run (idempotent)."""
    _cleanup_e2e_menu_data()
    yield


class TestAdminCreatesAndCustomerSees:
    def test_admin_creates_category_then_appears_in_api(self, page: Page, base_url, users):
        _login_admin(page, base_url, users)
        page.goto(f"{base_url}/dashboard/menu/categories/new/")
        page.fill("input[name='name']", "E2E Salads")
        page.fill("input[name='slug']", "e2e-salads")
        page.fill("input[name='display_order']", "0")
        page.check("input[name='is_active']")
        _submit_form(page)
        expect(page).to_have_url(f"{base_url}/dashboard/menu/categories/")

        resp = requests.get(f"{base_url}/api/v1/menu/categories/", timeout=5)
        assert resp.status_code == 200
        slugs = [c["slug"] for c in resp.json()]
        assert "e2e-salads" in slugs

    def test_admin_creates_dish_with_image_then_appears_in_api(
        self, page: Page, base_url, users
    ):
        _login_admin(page, base_url, users)
        # Ensure a category exists
        page.goto(f"{base_url}/dashboard/menu/categories/new/")
        page.fill("input[name='name']", "E2E Pizzas")
        page.fill("input[name='slug']", "e2e-pizzas")
        page.fill("input[name='display_order']", "0")
        page.check("input[name='is_active']")
        _submit_form(page)

        # Create item
        page.goto(f"{base_url}/dashboard/menu/items/new/")
        page.select_option("select[name='category']", label="E2E Pizzas")
        page.fill("input[name='name']", "E2E Margherita")
        page.fill("input[name='price']", "99.50")
        page.fill("input[name='cost']", "30")
        page.fill("input[name='prep_time_min']", "10")
        page.fill("textarea[name='tags']", "[]")
        page.set_input_files(
            "input[name='image']",
            files=[{"name": "img.png", "mimeType": "image/png", "buffer": _png_bytes()}],
        )
        page.check("input[name='is_available']")
        _submit_form(page)
        expect(page).to_have_url(f"{base_url}/dashboard/menu/items/")

        resp = requests.get(
            f"{base_url}/api/v1/menu/items/?category=e2e-pizzas", timeout=5
        )
        assert resp.status_code == 200
        names = [i["name"] for i in resp.json()["results"]]
        assert "E2E Margherita" in names

    def test_toggle_availability_affects_api(self, page: Page, base_url, users):
        _login_admin(page, base_url, users)
        page.goto(f"{base_url}/dashboard/menu/items/")
        # Locate the row containing E2E Margherita and click its toggle button
        row = page.locator("tr", has_text="E2E Margherita").first
        row.locator("form button").first.click()
        # After toggle, item should not be in API
        resp = requests.get(
            f"{base_url}/api/v1/menu/items/?category=e2e-pizzas", timeout=5
        )
        names = [i["name"] for i in resp.json()["results"]]
        assert "E2E Margherita" not in names

        # Toggle back
        page.goto(f"{base_url}/dashboard/menu/items/")
        row = page.locator("tr", has_text="E2E Margherita").first
        row.locator("form button").first.click()
        resp = requests.get(
            f"{base_url}/api/v1/menu/items/?category=e2e-pizzas", timeout=5
        )
        names = [i["name"] for i in resp.json()["results"]]
        assert "E2E Margherita" in names


class TestSearchAndFilters:
    def test_fuzzy_search_finds_typo(self, base_url):
        # Customer (no auth needed) searches with a typo
        resp = requests.get(f"{base_url}/api/v1/menu/items/?search=margerita", timeout=5)
        assert resp.status_code == 200
        names = [i["name"] for i in resp.json()["results"]]
        assert any("Margherita" in n for n in names)


class TestRoleGating:
    def test_cashier_blocked_from_dashboard_menu(self, page: Page, base_url, users):
        page.goto(f"{base_url}/login/")
        page.fill("input[name='email']", users["cashier"]["email"])
        page.fill("input[name='password']", users["cashier"]["password"])
        page.click("button[type='submit']")
        resp = page.goto(f"{base_url}/dashboard/menu/items/")
        assert resp.status == 403

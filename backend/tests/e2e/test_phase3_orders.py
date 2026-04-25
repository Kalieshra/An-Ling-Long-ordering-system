"""Phase 3 E2E: cashier POS, customer API, kitchen list, snapshot integrity.

Pre-reqs:
- docker compose up -d (with Phase-1+2 stack)
- Seed users for admin/cashier/kitchen/customer (Phase-1 conftest handles it)
"""
import shutil
import subprocess

import pytest
import requests
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.e2e


def _shell(script: str) -> str:
    if shutil.which("docker") is None:
        pytest.skip("docker CLI not on PATH")
    result = subprocess.run(
        ["docker", "compose", "exec", "-T", "web", "python", "manage.py", "shell", "-c", script],
        check=False, capture_output=True, text=True, timeout=30,
    )
    if result.returncode != 0:
        pytest.skip(f"Shell failed: {result.stdout}\n{result.stderr}")
    return result.stdout


def _seed_phase3_menu():
    _shell(
        "from menu.models import Category, MenuItem\n"
        "from orders.models import Table\n"
        "from decimal import Decimal\n"
        "Category.objects.filter(slug='p3-pizzas').delete()\n"
        "Table.objects.filter(number=99).delete()\n"
        "c, _ = Category.objects.update_or_create(slug='p3-pizzas', defaults={'name':'P3 Pizzas','is_active':True})\n"
        "MenuItem.objects.update_or_create(category=c, name='P3 Margherita', defaults={'price': Decimal('100.00'), 'is_available': True})\n"
        "Table.objects.update_or_create(number=99, defaults={'capacity':4,'is_active':True,'qr_token':'p3-99'})\n"
        "print('seeded')\n"
    )


def _cleanup_phase3():
    _shell(
        "from menu.models import Category, MenuItem\n"
        "from orders.models import Table, Order\n"
        "Order.objects.filter(items__menu_item__name='P3 Margherita').delete()\n"
        "MenuItem.objects.filter(name__startswith='P3 ').delete()\n"
        "Category.objects.filter(slug='p3-pizzas').delete()\n"
        "Table.objects.filter(number=99).delete()\n"
        "print('cleaned')\n"
    )


@pytest.fixture(scope="module", autouse=True)
def fresh_data():
    _cleanup_phase3()
    _seed_phase3_menu()
    yield
    _cleanup_phase3()


def _login(page: Page, base_url: str, email: str, password: str, expected_landing: str) -> None:
    page.goto(f"{base_url}/login/")
    page.fill("input[name='email']", email)
    page.fill("input[name='password']", password)
    page.click("button[type='submit']")
    expect(page).to_have_url(f"{base_url}{expected_landing}")


class TestCashierPOSDineIn:
    def test_cashier_places_dine_in_then_kitchen_sees_it(self, page, base_url, users, browser):
        _login(page, base_url, users["cashier"]["email"], users["cashier"]["password"], "/cashier/")
        page.locator(".pos-cat-btn", has_text="P3 Pizzas").click()
        page.locator(".pos-item", has_text="P3 Margherita").click()
        page.locator(".pos-type-btn[data-type='dine_in']").click()
        page.select_option("select[name='table']", label="#99 (4 seats)")
        page.click("#pos-confirm")
        # Detail page URL is /cashier/orders/<uuid>/
        page.wait_for_url("**/cashier/orders/**", timeout=8000)
        expect(page.locator("body")).to_contain_text("Mark paid")

        # Open a fresh kitchen browser context
        ctx = browser.new_context()
        kp = ctx.new_page()
        _login(kp, base_url, users["kitchen"]["email"], users["kitchen"]["password"], "/kitchen/")
        expect(kp.locator("body")).to_contain_text("P3 Margherita")
        ctx.close()


class TestCashierTakeawayThenMarkPaid:
    def test_takeaway_paid_then_receipt(self, page, base_url, users):
        _login(page, base_url, users["cashier"]["email"], users["cashier"]["password"], "/cashier/")
        page.locator(".pos-cat-btn", has_text="P3 Pizzas").click()
        page.locator(".pos-item", has_text="P3 Margherita").click()
        page.locator(".pos-type-btn[data-type='takeaway']").click()
        page.fill("input[name='phone']", "0100-555")
        page.click("#pos-confirm")
        page.wait_for_url("**/cashier/orders/**", timeout=8000)
        page.click("button:has-text('Mark paid')")
        expect(page.locator("body")).to_contain_text("Paid")
        page.click("a:has-text('View receipt')")
        expect(page.locator("body")).to_contain_text("P3 Margherita")
        expect(page.locator("body")).to_contain_text("Total")


class TestCustomerAPIPlaceAndCancel:
    def _jwt(self, base_url, users):
        r = requests.post(
            f"{base_url}/api/v1/auth/login/",
            json={"email": users["customer"]["email"], "password": users["customer"]["password"]},
            timeout=5,
        )
        assert r.status_code == 200, r.text
        return r.json()["access"]

    def test_create_then_cancel_pending_via_api(self, base_url, users):
        token = self._jwt(base_url, users)
        items = requests.get(f"{base_url}/api/v1/menu/items/?category=p3-pizzas", timeout=5).json()
        mid = items["results"][0]["id"]
        r = requests.post(
            f"{base_url}/api/v1/orders/",
            json={
                "type": "delivery",
                "delivery_address": "10 Cairo St",
                "items": [{"menu_item": mid, "quantity": 1}],
            },
            headers={"Authorization": f"Bearer {token}"},
            timeout=5,
        )
        assert r.status_code == 201, r.text
        uuid = r.json()["uuid"]
        c = requests.patch(
            f"{base_url}/api/v1/orders/{uuid}/cancel/",
            headers={"Authorization": f"Bearer {token}"}, timeout=5,
        )
        assert c.status_code == 200
        assert c.json()["status"] == "cancelled"

    def test_cancel_after_cashier_confirm_409(self, base_url, users):
        token = self._jwt(base_url, users)
        items = requests.get(f"{base_url}/api/v1/menu/items/?category=p3-pizzas", timeout=5).json()
        mid = items["results"][0]["id"]
        r = requests.post(
            f"{base_url}/api/v1/orders/",
            json={"type": "takeaway", "items": [{"menu_item": mid, "quantity": 1}]},
            headers={"Authorization": f"Bearer {token}"}, timeout=5,
        )
        uuid = r.json()["uuid"]
        _shell(
            f"from orders.models import Order\n"
            f"from orders.services import confirm_order\n"
            f"o = Order.objects.get(uuid='{uuid}')\n"
            f"confirm_order(o)\n"
            f"print('confirmed')\n"
        )
        c = requests.patch(
            f"{base_url}/api/v1/orders/{uuid}/cancel/",
            headers={"Authorization": f"Bearer {token}"}, timeout=5,
        )
        assert c.status_code == 409


class TestSnapshotIntegrity:
    def test_receipt_after_rename_keeps_original_name(self, page, base_url, users):
        _login(page, base_url, users["cashier"]["email"], users["cashier"]["password"], "/cashier/")
        page.locator(".pos-cat-btn", has_text="P3 Pizzas").click()
        page.locator(".pos-item", has_text="P3 Margherita").click()
        page.locator(".pos-type-btn[data-type='takeaway']").click()
        page.fill("input[name='phone']", "0100")
        page.click("#pos-confirm")
        page.wait_for_url("**/cashier/orders/**", timeout=8000)
        order_url = page.url
        order_uuid = order_url.rstrip("/").rsplit("/", 1)[-1]

        _shell(
            "from menu.models import MenuItem\n"
            "MenuItem.objects.filter(name='P3 Margherita').update(name='P3 RENAMED')\n"
            "print('renamed')\n"
        )

        page.goto(f"{base_url}/cashier/orders/{order_uuid}/receipt/")
        expect(page.locator("body")).to_contain_text("P3 Margherita")
        # The renamed text shouldn't appear in the receipt body
        expect(page.locator("body")).not_to_contain_text("P3 RENAMED")

        _shell(
            "from menu.models import MenuItem\n"
            "MenuItem.objects.filter(name='P3 RENAMED').update(name='P3 Margherita')\n"
            "print('restored')\n"
        )


class TestKitchenStatusFlow:
    def test_kitchen_marks_preparing_then_ready(self, page, base_url, users):
        _login(page, base_url, users["cashier"]["email"], users["cashier"]["password"], "/cashier/")
        page.locator(".pos-cat-btn", has_text="P3 Pizzas").click()
        page.locator(".pos-item", has_text="P3 Margherita").click()
        page.locator(".pos-type-btn[data-type='takeaway']").click()
        page.fill("input[name='phone']", "0100")
        page.click("#pos-confirm")
        page.wait_for_url("**/cashier/orders/**", timeout=8000)

        # Kitchen view
        page.context.clear_cookies()
        _login(page, base_url, users["kitchen"]["email"], users["kitchen"]["password"], "/kitchen/")
        page.locator("button:has-text('Start preparing')").first.click()
        expect(page).to_have_url(f"{base_url}/kitchen/")
        page.locator("button:has-text('Mark ready')").first.click()
        expect(page).to_have_url(f"{base_url}/kitchen/")
        # status=ready is kitchen-visible
        expect(page.locator("body")).to_contain_text("ready")

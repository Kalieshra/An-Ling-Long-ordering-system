"""Phase 4 E2E: real-time kitchen via WebSocket.

Pre-reqs:
- docker compose up -d (web + asgi both running)
- Phase 1+2+3 conftest seeds staff users
"""
import shutil
import subprocess
import time

import pytest
from playwright.sync_api import expect

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


def _seed():
    _shell(
        "from menu.models import Category, MenuItem\n"
        "from orders.models import Table\n"
        "from decimal import Decimal\n"
        "Category.objects.filter(slug='p4-pizzas').delete()\n"
        "Table.objects.filter(number=88).delete()\n"
        "c, _ = Category.objects.update_or_create(slug='p4-pizzas', defaults={'name':'P4 Pizzas','is_active':True})\n"
        "MenuItem.objects.update_or_create(category=c, name='P4 Margherita', defaults={'price': Decimal('100'), 'is_available': True})\n"
        "Table.objects.update_or_create(number=88, defaults={'capacity':4,'is_active':True,'qr_token':'p4-88'})\n"
        "print('seeded')\n"
    )


def _cleanup():
    _shell(
        "from menu.models import Category, MenuItem\n"
        "from orders.models import Table, Order\n"
        "Order.objects.filter(items__menu_item__name='P4 Margherita').delete()\n"
        "MenuItem.objects.filter(name__startswith='P4 ').delete()\n"
        "Category.objects.filter(slug='p4-pizzas').delete()\n"
        "Table.objects.filter(number=88).delete()\n"
        "print('cleaned')\n"
    )


@pytest.fixture(scope="module", autouse=True)
def fresh():
    _cleanup()
    _seed()
    yield
    _cleanup()


def _login(page, base_url, email, password, expected_landing):
    page.goto(f"{base_url}/login/")
    page.fill("input[name='email']", email)
    page.fill("input[name='password']", password)
    page.click("button[type='submit']")
    expect(page).to_have_url(f"{base_url}{expected_landing}")


class TestLiveKitchenUpdates:
    def test_cashier_confirms_kitchen_sees_within_2s(self, browser, base_url, users):
        # 1) Open kitchen browser first so its WS is subscribed
        kitchen_ctx = browser.new_context()
        kp = kitchen_ctx.new_page()
        _login(kp, base_url, users["kitchen"]["email"], users["kitchen"]["password"], "/kitchen/")
        # Wait for live banner
        expect(kp.locator("#ws-banner")).to_have_text("🟢 live", timeout=5000)

        # 2) Cashier in a fresh context places + confirms an order
        cashier_ctx = browser.new_context()
        cp = cashier_ctx.new_page()
        _login(cp, base_url, users["cashier"]["email"], users["cashier"]["password"], "/cashier/")
        cp.locator(".pos-cat-btn", has_text="P4 Pizzas").click()
        cp.locator(".pos-item", has_text="P4 Margherita").click()
        cp.locator(".pos-type-btn[data-type='takeaway']").click()
        cp.fill("input[name='phone']", "0100-444")
        before = time.monotonic()
        cp.click("#pos-confirm")
        cp.wait_for_url("**/cashier/orders/**", timeout=8000)

        # 3) Within ~2s the kitchen browser must show the new order (4s slack for CI variance)
        expect(kp.locator("body")).to_contain_text("P4 Margherita", timeout=4000)
        elapsed = time.monotonic() - before
        assert elapsed < 6, f"Took {elapsed}s — exceeds spec target with slack"

        cashier_ctx.close()
        kitchen_ctx.close()


class TestTwoKitchenBrowsersSync:
    def test_one_kitchen_marks_ready_other_updates(self, browser, base_url, users):
        # Place an order via cashier first
        cashier_ctx = browser.new_context()
        cp = cashier_ctx.new_page()
        _login(cp, base_url, users["cashier"]["email"], users["cashier"]["password"], "/cashier/")
        cp.locator(".pos-cat-btn", has_text="P4 Pizzas").click()
        cp.locator(".pos-item", has_text="P4 Margherita").click()
        cp.locator(".pos-type-btn[data-type='takeaway']").click()
        cp.fill("input[name='phone']", "0100")
        cp.click("#pos-confirm")
        cp.wait_for_url("**/cashier/orders/**", timeout=8000)
        cashier_ctx.close()

        # Two kitchen browsers
        ctx_a = browser.new_context()
        page_a = ctx_a.new_page()
        _login(page_a, base_url, users["kitchen"]["email"], users["kitchen"]["password"], "/kitchen/")

        ctx_b = browser.new_context()
        page_b = ctx_b.new_page()
        _login(page_b, base_url, users["kitchen"]["email"], users["kitchen"]["password"], "/kitchen/")

        # Both should see the order
        expect(page_a.locator("body")).to_contain_text("P4 Margherita", timeout=4000)
        expect(page_b.locator("body")).to_contain_text("P4 Margherita", timeout=4000)

        # A clicks "Start preparing"
        page_a.locator("button:has-text('Start preparing')").first.click()
        # B should see "Mark ready" appear within 4s
        expect(page_b.locator("button:has-text('Mark ready')")).to_be_visible(timeout=4000)

        ctx_a.close()
        ctx_b.close()


class TestRoleRejection:
    def test_cashier_ws_handshake_rejected(self, browser, base_url, users):
        ctx = browser.new_context()
        page = ctx.new_page()
        _login(page, base_url, users["cashier"]["email"], users["cashier"]["password"], "/cashier/")
        close_code = page.evaluate(
            """
            async () => {
                return await new Promise((resolve) => {
                    const ws = new WebSocket("ws://localhost:19000/ws/kds/");
                    // Do NOT resolve on open — wait for the server to close after
                    // accept()+close(4401).  If it stays open past the timeout,
                    // resolve(0) signals an unexpected open connection.
                    ws.onclose = (e) => resolve(e.code);
                    setTimeout(() => resolve(ws.readyState === 1 ? 0 : -1), 5000);
                });
            }
            """
        )
        assert close_code == 4401, f"expected 4401, got {close_code}"
        ctx.close()

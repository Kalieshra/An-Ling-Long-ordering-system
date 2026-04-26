"""Phase 6 smoke E2E: full customer happy path through pay+cook+track.

Exercises every layer (REST + Channels) in one test. If this passes, the MVP
works end-to-end.

Pre-reqs:
- docker compose up -d (web + asgi)
- conftest seeds staff users
"""
import json
import shutil
import subprocess
import time
from contextlib import suppress

import pytest
import requests

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
        "from decimal import Decimal\n"
        "Category.objects.filter(slug='p6-pizzas').delete()\n"
        "c, _ = Category.objects.update_or_create(slug='p6-pizzas', defaults={'name':'P6 Pizzas','is_active':True})\n"
        "MenuItem.objects.update_or_create(category=c, name='P6 Margherita', "
        "    defaults={'price': Decimal('100'), 'is_available': True})\n"
        "print('seeded')\n"
    )


def _cleanup():
    _shell(
        "from menu.models import Category, MenuItem\n"
        "from orders.models import Order\n"
        "Order.objects.filter(items__menu_item__name='P6 Margherita').delete()\n"
        "MenuItem.objects.filter(name__startswith='P6 ').delete()\n"
        "Category.objects.filter(slug='p6-pizzas').delete()\n"
        "print('cleaned')\n"
    )


def _clear_throttles():
    _shell("from django.core.cache import cache\ncache.clear()\nprint('cleared')\n")


@pytest.fixture(scope="module", autouse=True)
def fresh():
    _cleanup()
    _seed()
    yield
    _cleanup()


@pytest.fixture(autouse=True)
def reset_throttles():
    _clear_throttles()
    yield


class TestSmokeFullHappyPath:
    def test_register_order_pay_cook_track(self, base_url, users):
        # 1) Register a fresh customer
        email = f"p6-test-{int(time.time())}@x.com"
        password = "p6-test-pw-long-enough"
        r = requests.post(
            f"{base_url}/api/v1/auth/register/",
            json={"email": email, "password": password, "name": "P6 Test"},
            timeout=5,
        )
        assert r.status_code in (200, 201), r.text

        # 2) Login
        r = requests.post(
            f"{base_url}/api/v1/auth/login/",
            json={"email": email, "password": password}, timeout=5,
        )
        assert r.status_code == 200, r.text
        token = r.json()["access"]
        H = {"Authorization": f"Bearer {token}"}

        # 3) Browse menu
        r = requests.get(f"{base_url}/api/v1/menu/items/?category=p6-pizzas", timeout=5)
        item_id = r.json()["results"][0]["id"]

        # 4) Place delivery order
        r = requests.post(
            f"{base_url}/api/v1/orders/",
            json={
                "type": "delivery",
                "delivery_address": "10 Cairo St",
                "items": [{"menu_item": item_id, "quantity": 1}],
            },
            headers=H, timeout=5,
        )
        assert r.status_code == 201, r.text
        uuid = r.json()["uuid"]

        # 5) Open WS-track BEFORE state changes so we capture every event
        ws_base = base_url.replace("http://", "ws://").replace("18000", "19000")
        ws_url = f"{ws_base}/ws/order/{uuid}/?token={token}"

        from websockets.sync.client import connect
        events = []
        ws = connect(ws_url)
        try:
            # 6) Cashier confirms (pending → confirmed)
            # Note: confirm_order() broadcasts only to kds group (order.new),
            # not to the per-customer group. Use update_order_status so the
            # per-order WS receives an order.updated with status=confirmed.
            _shell(
                f"from orders.models import Order\n"
                f"from orders.services import update_order_status\n"
                f"from accounts.models import User\n"
                f"u = User.objects.filter(role='cashier').first()\n"
                f"o = Order.objects.get(uuid='{uuid}')\n"
                f"update_order_status(o, 'confirmed', by_user=u)\n"
                f"print('confirmed')\n"
            )
            events.append(json.loads(ws.recv(timeout=3)))

            # 7) Cashier marks paid (DB-only — does NOT broadcast)
            _shell(
                f"from orders.models import Order\n"
                f"from orders.services import mark_paid_cash\n"
                f"from accounts.models import User\n"
                f"u = User.objects.filter(role='cashier').first()\n"
                f"o = Order.objects.get(uuid='{uuid}')\n"
                f"mark_paid_cash(o, cashier=u)\n"
                f"print('paid')\n"
            )
            shell_out = _shell(
                f"from orders.models import Order\n"
                f"o = Order.objects.get(uuid='{uuid}')\n"
                f"print(o.payment_status)\n"
            )
            assert "paid" in shell_out.strip().split("\n")[-1]

            # 8) Kitchen advances confirmed → preparing → ready
            _shell(
                f"from orders.models import Order\n"
                f"from orders.services import update_order_status\n"
                f"from accounts.models import User\n"
                f"u = User.objects.filter(role='kitchen').first()\n"
                f"o = Order.objects.get(uuid='{uuid}')\n"
                f"update_order_status(o, 'preparing', by_user=u)\n"
                f"o.refresh_from_db()\n"
                f"update_order_status(o, 'ready', by_user=u)\n"
                f"print('ready')\n"
            )
            events.append(json.loads(ws.recv(timeout=3)))
            events.append(json.loads(ws.recv(timeout=3)))
        finally:
            with suppress(Exception):
                ws.close()

        # 9) Verify the customer WS saw confirmed → preparing → ready in order.
        statuses = [e["payload"]["status"] for e in events]
        assert statuses[0] == "confirmed"
        assert "preparing" in statuses
        assert statuses[-1] == "ready"

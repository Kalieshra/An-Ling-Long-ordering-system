"""Phase 5 E2E: full customer-API happy path + throttling + CORS.

Pre-reqs:
- docker compose up -d (web + asgi)
- Phase 1+ conftest seeds staff users
"""
import json
import shutil
import subprocess
import time

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
        "Category.objects.filter(slug='p5-pizzas').delete()\n"
        "c, _ = Category.objects.update_or_create(slug='p5-pizzas', defaults={'name':'P5 Pizzas','is_active':True})\n"
        "MenuItem.objects.update_or_create(category=c, name='P5 Margherita', "
        "    defaults={'price': Decimal('100'), 'is_available': True, 'tags': ['featured']})\n"
        "print('seeded')\n"
    )


def _cleanup():
    _shell(
        "from menu.models import Category, MenuItem\n"
        "from orders.models import Order\n"
        "Order.objects.filter(items__menu_item__name='P5 Margherita').delete()\n"
        "MenuItem.objects.filter(name__startswith='P5 ').delete()\n"
        "Category.objects.filter(slug='p5-pizzas').delete()\n"
        "print('cleaned')\n"
    )


def _clear_throttles():
    """Throttle counters live in the cache. Clear between tests so anon-rate
    leftovers from previous tests don't trigger 429s in subsequent ones."""
    _shell(
        "from django.core.cache import cache\n"
        "cache.clear()\n"
        "print('cleared')\n"
    )


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


class TestCustomerHappyPath:
    def _register(self, base_url, email, password):
        r = requests.post(
            f"{base_url}/api/v1/auth/register/",
            json={"email": email, "password": password, "name": "P5 Test"},
            timeout=5,
        )
        assert r.status_code in (200, 201), r.text
        return r.json()

    def _login(self, base_url, email, password):
        r = requests.post(
            f"{base_url}/api/v1/auth/login/",
            json={"email": email, "password": password}, timeout=5,
        )
        assert r.status_code == 200, r.text
        return r.json()["access"]

    def test_register_browse_order_track(self, base_url):
        email = f"p5-test-{int(time.time())}@x.com"
        password = "p5-test-pw-long-enough"

        # 1) Register
        self._register(base_url, email, password)
        token = self._login(base_url, email, password)
        H = {"Authorization": f"Bearer {token}"}

        # 2) Browse featured (cache miss)
        r1 = requests.get(f"{base_url}/api/v1/menu/featured/", timeout=5)
        assert r1.status_code == 200
        assert any(i["name"] == "P5 Margherita" for i in r1.json()["results"])

        # 3) Browse featured again (cache hit — same response)
        r2 = requests.get(f"{base_url}/api/v1/menu/featured/", timeout=5)
        assert r2.json() == r1.json()

        # 4) Browse by category
        r = requests.get(f"{base_url}/api/v1/menu/items/?category=p5-pizzas", timeout=5)
        assert r.status_code == 200
        items = r.json()["results"]
        item_id = items[0]["id"]

        # 5) Item detail
        r = requests.get(f"{base_url}/api/v1/menu/items/{item_id}/", timeout=5)
        assert r.status_code == 200

        # 6) Create delivery order
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
        order = r.json()
        uuid = order["uuid"]

        # 7) WS-connect to order-track and observe status changes.
        # The per-order consumer (OrderTrackConsumer) only relays `order.updated`
        # messages sent to the `order_{uuid}` channel group.
        # - confirm_order() → on_order_confirmed() → broadcasts to `kds` group only
        # - update_order_status() → _broadcast_status() → broadcasts to BOTH `kds`
        #   AND `order_{uuid}` group.
        # So we drive all three transitions (confirmed, preparing, ready) via
        # update_order_status so each one produces an `order.updated` event on
        # the per-customer WS connection.
        #
        # Use websockets.sync.client (no asyncio) so this plain `def` test stays
        # compatible with the Playwright event loop created by pytest-playwright in
        # the full suite (asyncio_mode=auto + running playwright loop = conflict).
        ws_base = base_url.replace("http://", "ws://").replace("18000", "19000")
        ws_url = f"{ws_base}/ws/order/{uuid}/?token={token}"

        from websockets.sync.client import connect as ws_connect  # noqa: PLC0415
        with ws_connect(ws_url) as ws:
            # Drive all three transitions in one shell call so the
            # on_commit handlers fire inside the container's DB transaction.
            _shell(
                f"from orders.models import Order\n"
                f"from orders.services import update_order_status\n"
                f"from accounts.models import User\n"
                f"cashier = User.objects.filter(role='cashier').first()\n"
                f"kitchen = User.objects.filter(role='kitchen').first()\n"
                f"o = Order.objects.get(uuid='{uuid}')\n"
                f"update_order_status(o, 'confirmed', by_user=cashier)\n"
                f"o.refresh_from_db()\n"
                f"update_order_status(o, 'preparing', by_user=kitchen)\n"
                f"o.refresh_from_db()\n"
                f"update_order_status(o, 'ready', by_user=kitchen)\n"
                f"print('done')\n"
            )
            msg1 = ws.recv(timeout=10)
            msg2 = ws.recv(timeout=10)
            msg3 = ws.recv(timeout=10)

        events = [json.loads(m) for m in (msg1, msg2, msg3)]
        statuses = [e["payload"]["status"] for e in events]
        assert "confirmed" in statuses
        assert "preparing" in statuses
        assert "ready" in statuses


class TestLoginThrottling:
    def test_6th_login_returns_429(self, base_url, users):
        email = users["customer"]["email"]
        for _ in range(5):
            requests.post(f"{base_url}/api/v1/auth/login/",
                          json={"email": email, "password": "wrong"}, timeout=5)
        r = requests.post(f"{base_url}/api/v1/auth/login/",
                          json={"email": email, "password": "wrong"}, timeout=5)
        assert r.status_code == 429


class TestCORS:
    def test_allowed_origin_preflight(self, base_url):
        # Read the running container's CORS_ALLOWED_ORIGINS
        env_origins = _shell(
            "from django.conf import settings\nprint(','.join(settings.CORS_ALLOWED_ORIGINS))\n"
        ).strip()
        # The shell command prints "cleared\n" first (from the autouse fixture clearing throttles),
        # then the actual output. Take the LAST non-empty line.
        lines = [ln for ln in env_origins.split("\n") if ln.strip()]
        env_origins = lines[-1] if lines else ""
        if not env_origins:
            pytest.skip("CORS_ALLOWED_ORIGINS empty in env — set one to test allow-list")
        first_origin = env_origins.split(",")[0]

        r = requests.options(
            f"{base_url}/api/v1/menu/categories/",
            headers={
                "Origin": first_origin,
                "Access-Control-Request-Method": "GET",
            },
            timeout=5,
        )
        assert r.status_code == 200
        assert r.headers.get("Access-Control-Allow-Origin") == first_origin

    def test_disallowed_origin_blocked(self, base_url):
        r = requests.options(
            f"{base_url}/api/v1/menu/categories/",
            headers={
                "Origin": "http://evil.example.com",
                "Access-Control-Request-Method": "GET",
            },
            timeout=5,
        )
        assert "Access-Control-Allow-Origin" not in r.headers

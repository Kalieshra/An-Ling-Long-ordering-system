"""Integration tests for cashier-side order endpoints under /cashier/."""
import json
from decimal import Decimal

import pytest
from django.test import Client
from menu.models import Category, MenuItem
from orders.models import Order, Table

pytestmark = pytest.mark.django_db


@pytest.fixture
def cashier(django_user_model):
    return django_user_model.objects.create_user(
        email="cash@x.com", password="cash-pw-long-enough", role="cashier"
    )


@pytest.fixture
def admin_user(django_user_model):
    return django_user_model.objects.create_user(
        email="admin@x.com", password="admin-pw-long-enough", role="admin"
    )


@pytest.fixture
def cashier_client(cashier):
    c = Client()
    assert c.login(email="cash@x.com", password="cash-pw-long-enough")
    return c


@pytest.fixture
def category():
    return Category.objects.create(name="Pizzas", slug="pizzas")


@pytest.fixture
def margherita(category):
    return MenuItem.objects.create(
        category=category, name="Margherita", price=Decimal("100")
    )


@pytest.fixture
def table():
    return Table.objects.create(number=1, capacity=4)


class TestCashierPOSView:
    def test_renders_with_menu_data(self, cashier_client, margherita, table):
        resp = cashier_client.get("/cashier/")
        assert resp.status_code == 200
        body = resp.content.decode()
        assert "pos-root" in body
        assert "Margherita" in body
        # Tables are rendered into the <select> element
        assert "#1" in body

    def test_admin_blocked(self, admin_user):
        c = Client()
        c.login(email="admin@x.com", password="admin-pw-long-enough")
        resp = c.get("/cashier/")
        assert resp.status_code == 403


class TestCashierOrderCreate:
    def test_dine_in_creates_and_confirms(self, cashier_client, margherita, table):
        body = {
            "type": "dine_in",
            "table": table.id,
            "items": [{"menu_item": margherita.id, "quantity": 2, "modifiers": []}],
        }
        resp = cashier_client.post(
            "/cashier/orders/create/", data=json.dumps(body), content_type="application/json"
        )
        assert resp.status_code == 200, resp.content
        data = resp.json()
        assert "redirect" in data
        order = Order.objects.get(uuid=data["uuid"])
        assert order.status == Order.Status.CONFIRMED
        assert order.cashier is not None
        assert order.table == table
        assert order.subtotal == Decimal("200.00")

    def test_empty_cart_400(self, cashier_client):
        resp = cashier_client.post(
            "/cashier/orders/create/", data=json.dumps({"type": "takeaway", "items": []}),
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_takeaway_no_table(self, cashier_client, margherita):
        body = {
            "type": "takeaway",
            "items": [{"menu_item": margherita.id, "quantity": 1, "modifiers": []}],
            "customer_phone": "010-12345",
        }
        resp = cashier_client.post(
            "/cashier/orders/create/", data=json.dumps(body), content_type="application/json"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["uuid"]

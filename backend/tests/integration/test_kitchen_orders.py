"""Integration tests for the kitchen list at /kitchen/ + status transitions."""
from decimal import Decimal

import pytest
from django.test import Client
from menu.models import Category, MenuItem
from orders.models import Order

pytestmark = pytest.mark.django_db


@pytest.fixture
def kitchen(django_user_model):
    return django_user_model.objects.create_user(
        email="kit@x.com", password="kit-pw-long-enough", role="kitchen"
    )


@pytest.fixture
def cashier(django_user_model):
    return django_user_model.objects.create_user(
        email="cash@x.com", password="cash-pw-long-enough", role="cashier"
    )


@pytest.fixture
def kitchen_client(kitchen):
    c = Client()
    c.login(email="kit@x.com", password="kit-pw-long-enough")
    return c


@pytest.fixture
def category():
    return Category.objects.create(name="Pizzas", slug="pizzas")


@pytest.fixture
def margherita(category):
    return MenuItem.objects.create(
        category=category, name="Margherita", price=Decimal("100")
    )


def _make_order(margherita, status, number):
    from orders.services import confirm_order, create_order, transition_status
    o = create_order(
        cart=[{"menu_item": margherita.id, "quantity": 1, "modifiers": []}],
        order_type=Order.Type.TAKEAWAY,
    )
    if status == Order.Status.CONFIRMED:
        confirm_order(o)
    elif status == Order.Status.PREPARING:
        confirm_order(o)
        transition_status(o, Order.Status.PREPARING, by_user=None)
    elif status == Order.Status.READY:
        confirm_order(o)
        transition_status(o, Order.Status.PREPARING, by_user=None)
        transition_status(o, Order.Status.READY, by_user=None)
    o.number = number
    o.save(update_fields=["number"])
    return o


class TestKitchenList:
    def test_lists_kitchen_visible_orders(self, kitchen_client, margherita):
        _make_order(margherita, Order.Status.CONFIRMED, "K-1")
        _make_order(margherita, Order.Status.PREPARING, "K-2")
        _make_order(margherita, Order.Status.READY, "K-3")
        # SERVED should NOT show
        served = _make_order(margherita, Order.Status.READY, "K-4")
        from orders.services import transition_status
        transition_status(served, Order.Status.SERVED, by_user=None)

        resp = kitchen_client.get("/kitchen/")
        assert resp.status_code == 200
        body = resp.content.decode()
        assert "K-1" in body and "K-2" in body and "K-3" in body
        assert "K-4" not in body

    def test_cashier_blocked(self, cashier):
        c = Client()
        c.login(email="cash@x.com", password="cash-pw-long-enough")
        resp = c.get("/kitchen/")
        assert resp.status_code == 403


class TestKitchenStatusTransitions:
    def test_confirmed_to_preparing(self, kitchen_client, margherita):
        o = _make_order(margherita, Order.Status.CONFIRMED, "K-x")
        resp = kitchen_client.post(
            f"/kitchen/orders/{o.uuid}/status/",
            data={"status": "preparing"},
        )
        assert resp.status_code == 302
        o.refresh_from_db()
        assert o.status == Order.Status.PREPARING

    def test_invalid_transition_400(self, kitchen_client, margherita):
        o = _make_order(margherita, Order.Status.CONFIRMED, "K-y")
        resp = kitchen_client.post(
            f"/kitchen/orders/{o.uuid}/status/", data={"status": "ready"},
        )
        assert resp.status_code == 400

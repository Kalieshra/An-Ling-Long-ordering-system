"""Customer JWT API integration tests for /api/v1/orders/."""
from decimal import Decimal

import pytest
from menu.models import Category, MenuItem, ModifierGroup, ModifierOption
from orders.models import Order
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db


@pytest.fixture
def category():
    return Category.objects.create(name="Pizzas", slug="pizzas")


@pytest.fixture
def margherita(category):
    return MenuItem.objects.create(
        category=category, name="Margherita", price=Decimal("100.00")
    )


@pytest.fixture
def size_group(margherita):
    return ModifierGroup.objects.create(menu_item=margherita, name="Size", is_required=True)


@pytest.fixture
def large(size_group):
    return ModifierOption.objects.create(group=size_group, name="Large", price_delta=Decimal("30"))


@pytest.fixture
def customer(django_user_model):
    return django_user_model.objects.create_user(
        email="alice@x.com", password="alice-pw-long-enough", role="customer"
    )


@pytest.fixture
def cashier(django_user_model):
    return django_user_model.objects.create_user(
        email="cash@x.com", password="cash-pw-long-enough", role="cashier"
    )


def _jwt_login(client: APIClient, email: str, password: str) -> str:
    resp = client.post("/api/v1/auth/login/", {"email": email, "password": password}, format="json")
    assert resp.status_code == 200, resp.data
    return resp.data["access"]


@pytest.fixture
def auth_client(customer):
    c = APIClient()
    token = _jwt_login(c, "alice@x.com", "alice-pw-long-enough")
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return c


class TestCreateOrder:
    def test_takeaway_creates_pending_with_correct_totals(self, auth_client, margherita, large):
        body = {
            "type": "takeaway",
            "items": [{"menu_item": margherita.id, "quantity": 2, "modifiers": [large.id]}],
            "customer_phone": "0100",
        }
        resp = auth_client.post("/api/v1/orders/", body, format="json")
        assert resp.status_code == 201, resp.data
        assert resp.data["status"] == "pending"
        assert Decimal(resp.data["subtotal"]) == Decimal("260.00")  # (100+30)*2
        assert Decimal(resp.data["tax"]) == Decimal("36.40")
        assert Decimal(resp.data["total"]) == Decimal("296.40")
        assert "uuid" in resp.data
        assert "number" in resp.data

    def test_delivery_requires_address(self, auth_client, margherita):
        resp = auth_client.post(
            "/api/v1/orders/",
            {"type": "delivery", "items": [{"menu_item": margherita.id, "quantity": 1}]},
            format="json",
        )
        assert resp.status_code == 400
        assert "address" in str(resp.data).lower()

    def test_dine_in_via_customer_api_rejected(self, auth_client, margherita):
        resp = auth_client.post(
            "/api/v1/orders/",
            {"type": "dine_in", "items": [{"menu_item": margherita.id, "quantity": 1}]},
            format="json",
        )
        assert resp.status_code == 400

    def test_unavailable_item_400(self, auth_client, margherita):
        margherita.is_available = False
        margherita.save()
        resp = auth_client.post(
            "/api/v1/orders/",
            {"type": "takeaway", "items": [{"menu_item": margherita.id, "quantity": 1}]},
            format="json",
        )
        assert resp.status_code == 400

    def test_anonymous_post_401(self, margherita):
        c = APIClient()
        resp = c.post(
            "/api/v1/orders/",
            {"type": "takeaway", "items": [{"menu_item": margherita.id, "quantity": 1}]},
            format="json",
        )
        assert resp.status_code == 401

    def test_cashier_jwt_post_403(self, cashier, margherita):
        c = APIClient()
        token = _jwt_login(c, "cash@x.com", "cash-pw-long-enough")
        c.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        resp = c.post(
            "/api/v1/orders/",
            {"type": "takeaway", "items": [{"menu_item": margherita.id, "quantity": 1}]},
            format="json",
        )
        assert resp.status_code == 403


class TestListAndRetrieve:
    def test_list_returns_only_my_orders_paginated(self, auth_client, customer, margherita):
        # mine
        for _ in range(3):
            Order.objects.create(
                customer=customer, order_type=Order.Type.TAKEAWAY,
                status=Order.Status.PENDING, number=f"mine-{_}",
            )
        # someone else's
        Order.objects.create(
            order_type=Order.Type.TAKEAWAY, status=Order.Status.PENDING, number="other-1",
        )
        resp = auth_client.get("/api/v1/orders/")
        assert resp.status_code == 200
        nums = [o["number"] for o in resp.data["results"]]
        assert all(n.startswith("mine-") for n in nums)
        assert resp.data["count"] == 3

    def test_retrieve_other_customer_404(self, auth_client):
        other = Order.objects.create(
            order_type=Order.Type.TAKEAWAY, status=Order.Status.PENDING, number="other-1"
        )
        resp = auth_client.get(f"/api/v1/orders/{other.uuid}/")
        assert resp.status_code == 404

    def test_retrieve_uses_uuid_not_pk(self, auth_client, customer):
        o = Order.objects.create(
            customer=customer, order_type=Order.Type.TAKEAWAY,
            status=Order.Status.PENDING, number="mine-1",
        )
        resp = auth_client.get(f"/api/v1/orders/{o.uuid}/")
        assert resp.status_code == 200
        assert resp.data["number"] == "mine-1"


class TestCancel:
    def test_cancel_pending_works(self, auth_client, customer):
        o = Order.objects.create(
            customer=customer, order_type=Order.Type.TAKEAWAY,
            status=Order.Status.PENDING, number="mine-1",
        )
        resp = auth_client.patch(f"/api/v1/orders/{o.uuid}/cancel/")
        assert resp.status_code == 200
        o.refresh_from_db()
        assert o.status == Order.Status.CANCELLED

    def test_cancel_after_confirmed_409(self, auth_client, customer):
        o = Order.objects.create(
            customer=customer, order_type=Order.Type.TAKEAWAY,
            status=Order.Status.CONFIRMED, number="mine-2",
        )
        resp = auth_client.patch(f"/api/v1/orders/{o.uuid}/cancel/")
        assert resp.status_code == 409

    def test_cancel_other_customer_404(self, auth_client):
        other = Order.objects.create(
            order_type=Order.Type.TAKEAWAY,
            status=Order.Status.PENDING,
            number="other-1",
        )
        resp = auth_client.patch(f"/api/v1/orders/{other.uuid}/cancel/")
        assert resp.status_code == 404


class TestSnapshotAndUnavailable:
    def test_snapshot_survives_menu_rename(self, auth_client, margherita):
        resp = auth_client.post(
            "/api/v1/orders/",
            {"type": "takeaway", "items": [{"menu_item": margherita.id, "quantity": 1}]},
            format="json",
        )
        uuid = resp.data["uuid"]
        margherita.name = "Renamed Pizza"
        margherita.price = Decimal("999.00")
        margherita.save()
        detail = auth_client.get(f"/api/v1/orders/{uuid}/")
        snap_items = detail.data["snapshot"]["items"]
        assert snap_items[0]["name"] == "Margherita"
        assert snap_items[0]["unit_price"] == "100.00"

    def test_unavailable_item_400_via_api(self, auth_client, margherita):
        margherita.is_available = False
        margherita.save()
        resp = auth_client.post(
            "/api/v1/orders/",
            {"type": "takeaway", "items": [{"menu_item": margherita.id, "quantity": 1}]},
            format="json",
        )
        assert resp.status_code == 400

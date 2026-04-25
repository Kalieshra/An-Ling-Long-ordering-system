"""Unit tests for orders.services."""
from decimal import Decimal

import pytest
from menu.models import Category, MenuItem, ModifierGroup, ModifierOption
from orders.exceptions import OrderValidationError
from orders.models import Order
from orders.services import create_order

pytestmark = pytest.mark.django_db


@pytest.fixture
def pizzas():
    return Category.objects.create(name="Pizzas", slug="pizzas")


@pytest.fixture
def margherita(pizzas):
    return MenuItem.objects.create(
        category=pizzas, name="Margherita", price=Decimal("100.00")
    )


@pytest.fixture
def size_group(margherita):
    return ModifierGroup.objects.create(menu_item=margherita, name="Size", is_required=True)


@pytest.fixture
def large(size_group):
    return ModifierOption.objects.create(
        group=size_group, name="Large", price_delta=Decimal("30.00")
    )


@pytest.fixture
def small(size_group):
    return ModifierOption.objects.create(
        group=size_group, name="Small", price_delta=Decimal("0.00")
    )


@pytest.fixture
def cashier_user(django_user_model):
    return django_user_model.objects.create_user(
        email="cash@x.com", password="pw-long-enough", role="cashier"
    )


@pytest.fixture
def customer_user(django_user_model):
    return django_user_model.objects.create_user(
        email="cust@x.com", password="pw-long-enough", role="customer"
    )


def _line(item, qty, mod_ids=None, notes=""):
    return {"menu_item": item.id, "quantity": qty, "modifiers": mod_ids or [], "notes": notes}


class TestCreateOrderTotals:
    def test_subtotal_tax_total_for_one_line(self, margherita, cashier_user):
        order = create_order(
            cart=[_line(margherita, 2)],
            cashier=cashier_user,
            order_type=Order.Type.TAKEAWAY,
        )
        # 100 * 2 = 200; tax = 200 * 0.14 = 28; total = 228
        assert order.subtotal == Decimal("200.00")
        assert order.tax == Decimal("28.00")
        assert order.total == Decimal("228.00")
        assert order.status == Order.Status.DRAFT

    def test_subtotal_includes_modifier_price_deltas(
        self, margherita, large, cashier_user
    ):
        order = create_order(
            cart=[_line(margherita, 1, [large.id])],
            cashier=cashier_user,
            order_type=Order.Type.TAKEAWAY,
        )
        # (100 + 30) * 1 = 130; tax = 130 * 0.14 = 18.20; total = 148.20
        assert order.subtotal == Decimal("130.00")
        assert order.tax == Decimal("18.20")
        assert order.total == Decimal("148.20")

    def test_tax_rounds_half_up_to_two_dp(self, pizzas, cashier_user):
        # Price 33.33 * 1 = 33.33; tax = 4.6662 → rounds to 4.67
        cheap = MenuItem.objects.create(category=pizzas, name="C", price=Decimal("33.33"))
        order = create_order(
            cart=[_line(cheap, 1)], cashier=cashier_user, order_type=Order.Type.TAKEAWAY,
        )
        assert order.tax == Decimal("4.67")
        assert order.total == Decimal("38.00")


class TestCreateOrderSnapshot:
    def test_snapshot_freezes_name_price_and_modifier_label(
        self, margherita, large, cashier_user
    ):
        order = create_order(
            cart=[_line(margherita, 1, [large.id])],
            cashier=cashier_user,
            order_type=Order.Type.TAKEAWAY,
        )
        snap = order.snapshot
        assert snap["tax_rate"] == "0.14"
        assert len(snap["items"]) == 1
        line = snap["items"][0]
        assert line["name"] == "Margherita"
        assert line["unit_price"] == "100.00"
        assert line["quantity"] == 1
        assert line["modifiers"] == [
            {"option_id": large.id, "name": "Large", "price_delta": "30.00"}
        ]

    def test_snapshot_unaffected_by_later_rename(self, margherita, cashier_user):
        order = create_order(
            cart=[_line(margherita, 1)],
            cashier=cashier_user, order_type=Order.Type.TAKEAWAY,
        )
        margherita.name = "Renamed"
        margherita.price = Decimal("999.00")
        margherita.save()
        order.refresh_from_db()
        assert order.snapshot["items"][0]["name"] == "Margherita"
        assert order.snapshot["items"][0]["unit_price"] == "100.00"


class TestCreateOrderPersistence:
    def test_persists_order_items_with_unit_price_at_time_of_order(
        self, margherita, large, cashier_user
    ):
        order = create_order(
            cart=[_line(margherita, 2, [large.id])],
            cashier=cashier_user,
            order_type=Order.Type.TAKEAWAY,
        )
        items = list(order.items.all())
        assert len(items) == 1
        assert items[0].quantity == 2
        assert items[0].unit_price == Decimal("100.00")
        mods = list(items[0].modifiers.all())
        assert len(mods) == 1
        assert mods[0].price_delta == Decimal("30.00")

    def test_assigns_daily_order_number(self, margherita, cashier_user):
        order = create_order(
            cart=[_line(margherita, 1)],
            cashier=cashier_user, order_type=Order.Type.TAKEAWAY,
        )
        assert order.number  # non-empty
        assert "-" in order.number  # YYYYMMDD-NNNN


class TestCreateOrderValidation:
    def test_empty_cart_raises(self, cashier_user):
        with pytest.raises(OrderValidationError, match="empty"):
            create_order(cart=[], cashier=cashier_user, order_type=Order.Type.TAKEAWAY)

    def test_unavailable_item_raises(self, margherita, cashier_user):
        margherita.is_available = False
        margherita.save()
        with pytest.raises(OrderValidationError, match="unavailable"):
            create_order(
                cart=[_line(margherita, 1)],
                cashier=cashier_user,
                order_type=Order.Type.TAKEAWAY,
            )

    def test_unknown_item_raises(self, cashier_user):
        with pytest.raises(OrderValidationError, match="not found"):
            create_order(
                cart=[{"menu_item": 999999, "quantity": 1, "modifiers": []}],
                cashier=cashier_user, order_type=Order.Type.TAKEAWAY,
            )

    def test_modifier_belonging_to_other_item_raises(
        self, margherita, large, pizzas, cashier_user
    ):
        other = MenuItem.objects.create(category=pizzas, name="Other", price=Decimal("50"))
        with pytest.raises(OrderValidationError, match="modifier"):
            create_order(
                cart=[_line(other, 1, [large.id])],
                cashier=cashier_user,
                order_type=Order.Type.TAKEAWAY,
            )

    def test_dine_in_requires_table(self, margherita, cashier_user):
        with pytest.raises(OrderValidationError, match="table"):
            create_order(
                cart=[_line(margherita, 1)],
                cashier=cashier_user, order_type=Order.Type.DINE_IN,
            )

    def test_delivery_requires_address(self, margherita, customer_user):
        with pytest.raises(OrderValidationError, match="address"):
            create_order(
                cart=[_line(margherita, 1)],
                customer=customer_user, order_type=Order.Type.DELIVERY,
            )

    def test_zero_quantity_raises(self, margherita, cashier_user):
        with pytest.raises(OrderValidationError, match="quantity"):
            create_order(
                cart=[_line(margherita, 0)],
                cashier=cashier_user,
                order_type=Order.Type.TAKEAWAY,
            )

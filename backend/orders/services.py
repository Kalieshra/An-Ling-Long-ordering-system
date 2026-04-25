"""Service layer for orders. The only place that mutates Order state.

Both the cashier POS view and the customer JWT API call these functions, so
side effects (and — in Phase 4 — WebSocket broadcasts) are identical.
"""
from __future__ import annotations

from collections.abc import Iterable
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from menu.models import MenuItem, ModifierOption

from .exceptions import InvalidTransition, OrderValidationError
from .models import Order, OrderItem, OrderItemModifier, Table

CENTS = Decimal("0.01")


def _q(amount: Decimal) -> Decimal:
    return amount.quantize(CENTS, rounding=ROUND_HALF_UP)


def _calc_totals(lines: list[dict]) -> tuple[Decimal, Decimal, Decimal]:
    subtotal = Decimal("0")
    for line in lines:
        unit = line["_unit_price"]
        mod_total = sum((m["price_delta"] for m in line["_modifiers"]), Decimal("0"))
        subtotal += (unit + mod_total) * Decimal(line["quantity"])
    subtotal = _q(subtotal)
    tax = _q(subtotal * settings.RMS_TAX_RATE)
    total = _q(subtotal + tax)  # service_charge=0, discount=0 in MVP
    return subtotal, tax, total


def _build_snapshot(lines: list[dict]) -> dict:
    items_snap = []
    for line in lines:
        unit = line["_unit_price"]
        mods = [
            {
                "option_id": m["option_id"],
                "name": m["name"],
                "price_delta": str(m["price_delta"]),
            }
            for m in line["_modifiers"]
        ]
        line_subtotal = (
            unit + sum((m["price_delta"] for m in line["_modifiers"]), Decimal("0"))
        ) * Decimal(line["quantity"])
        items_snap.append({
            "menu_item_id": line["_menu_item"].id,
            "name": line["_menu_item"].name,
            "name_ar": line["_menu_item"].name_ar,
            "category": line["_menu_item"].category.name,
            "quantity": line["quantity"],
            "unit_price": str(unit),
            "notes": line.get("notes", ""),
            "modifiers": mods,
            "line_subtotal": str(_q(line_subtotal)),
        })
    return {"tax_rate": str(settings.RMS_TAX_RATE), "items": items_snap}


def _validate_and_resolve(
    cart: Iterable[dict], order_type: str, table, delivery_address: str
) -> list[dict]:
    cart = list(cart)
    if not cart:
        raise OrderValidationError("Cart is empty.")

    if order_type == Order.Type.DINE_IN and table is None:
        raise OrderValidationError("Dine-in requires a table.")
    if order_type == Order.Type.DELIVERY and not delivery_address:
        raise OrderValidationError("Delivery requires a delivery address.")

    resolved: list[dict] = []
    for line in cart:
        qty = int(line.get("quantity", 0))
        if qty <= 0:
            raise OrderValidationError("Item quantity must be positive.")

        try:
            mi = MenuItem.objects.select_related("category").get(id=line["menu_item"])
        except MenuItem.DoesNotExist:
            raise OrderValidationError(f"Menu item {line['menu_item']} not found.") from None
        if not mi.is_available or not mi.category.is_active:
            raise OrderValidationError(f"Menu item '{mi.name}' is unavailable.")

        mod_ids = list(line.get("modifiers", []) or [])
        mods = list(ModifierOption.objects.filter(id__in=mod_ids).select_related("group"))
        if len(mods) != len(mod_ids):
            raise OrderValidationError("Unknown modifier option.")
        for opt in mods:
            if opt.group.menu_item_id != mi.id:
                raise OrderValidationError(
                    f"modifier '{opt.name}' does not belong to '{mi.name}'."
                )
            if not opt.is_available:
                raise OrderValidationError(f"Modifier '{opt.name}' is unavailable.")

        resolved.append({
            "_menu_item": mi,
            "_unit_price": mi.price,
            "_modifiers": [
                {"option_id": m.id, "name": m.name, "price_delta": m.price_delta}
                for m in mods
            ],
            "quantity": qty,
            "notes": (line.get("notes") or "")[:200],
        })
    return resolved


@transaction.atomic
def create_order(
    cart: Iterable[dict],
    *,
    cashier=None,
    customer=None,
    table: Table | None = None,
    order_type: str,
    delivery_address: str = "",
    customer_phone: str = "",
    notes: str = "",
    initial_status: str = Order.Status.DRAFT,
) -> Order:
    """Create a new Order in the given starting status.

    `cart` is an iterable of dicts shaped::

        {"menu_item": <id>, "quantity": <int>, "modifiers": [<option_id>, ...], "notes": "..."}

    Money math is done with Decimal+ROUND_HALF_UP. The `snapshot` JSONB
    immortalises every line so a future menu rename does not break the receipt.
    """
    lines = _validate_and_resolve(cart, order_type, table, delivery_address)
    subtotal, tax, total = _calc_totals(lines)
    snapshot = _build_snapshot(lines)

    order = Order.objects.create(
        cashier=cashier,
        customer=customer,
        table=table,
        order_type=order_type,
        status=initial_status,
        subtotal=subtotal,
        tax=tax,
        total=total,
        delivery_address=delivery_address,
        customer_phone=customer_phone,
        notes=notes,
        snapshot=snapshot,
    )
    order.number = Order.next_number_for()
    order.save(update_fields=["number"])

    for line in lines:
        oi = OrderItem.objects.create(
            order=order,
            menu_item=line["_menu_item"],
            quantity=line["quantity"],
            unit_price=line["_unit_price"],
            notes=line["notes"],
        )
        for m in line["_modifiers"]:
            OrderItemModifier.objects.create(
                order_item=oi, option_id=m["option_id"], price_delta=m["price_delta"]
            )

    return order


_ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    Order.Status.DRAFT: {Order.Status.CONFIRMED, Order.Status.CANCELLED},
    Order.Status.PENDING: {Order.Status.CONFIRMED, Order.Status.CANCELLED},
    Order.Status.CONFIRMED: {Order.Status.PREPARING},
    Order.Status.PREPARING: {Order.Status.READY, Order.Status.CANCELLED},
    Order.Status.READY: {Order.Status.SERVED},
    Order.Status.SERVED: set(),
    Order.Status.CANCELLED: set(),
}


def _assert_transition(order: Order, target: str) -> None:
    if target not in _ALLOWED_TRANSITIONS.get(order.status, set()):
        raise InvalidTransition(
            f"Cannot move order {order.number} from {order.status} to {target}."
        )


@transaction.atomic
def confirm_order(order: Order) -> Order:
    """Move a DRAFT or PENDING order to CONFIRMED. Phase 4 will broadcast here."""
    _assert_transition(order, Order.Status.CONFIRMED)
    order.status = Order.Status.CONFIRMED
    order.confirmed_at = timezone.now()
    order.save(update_fields=["status", "confirmed_at"])
    return order


@transaction.atomic
def mark_paid_cash(order: Order, *, cashier) -> Order:
    if order.payment_status == Order.PaymentStatus.PAID:
        raise InvalidTransition(f"Order {order.number} is already paid.")
    order.payment_status = Order.PaymentStatus.PAID
    order.cashier = cashier
    order.save(update_fields=["payment_status", "cashier"])
    return order


@transaction.atomic
def cancel_order(order: Order) -> Order:
    _assert_transition(order, Order.Status.CANCELLED)
    order.status = Order.Status.CANCELLED
    order.save(update_fields=["status"])
    return order


@transaction.atomic
def transition_status(order: Order, target: str, *, by_user) -> Order:
    """Generic kitchen-driven state advance. Sets ready_at / served_at when relevant."""
    _assert_transition(order, target)
    order.status = target
    fields = ["status"]
    if target == Order.Status.READY:
        order.ready_at = timezone.now()
        fields.append("ready_at")
    elif target == Order.Status.SERVED:
        order.served_at = timezone.now()
        fields.append("served_at")
    order.save(update_fields=fields)
    return order

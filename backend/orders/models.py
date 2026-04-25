"""Order, OrderItem, OrderItemModifier, and Table models.

State machine (Order.status):
    DRAFT      → CONFIRMED | CANCELLED
    PENDING    → CONFIRMED | CANCELLED         (customer-API orders awaiting cashier ack)
    CONFIRMED  → PREPARING | CANCELLED
    PREPARING  → READY | CANCELLED
    READY      → SERVED
    SERVED     → (terminal)
    CANCELLED  → (terminal)
"""
from __future__ import annotations

import uuid as uuid_lib
from datetime import date as date_cls
from decimal import Decimal

from django.conf import settings
from django.db import models

from .managers import OrderManager


class Table(models.Model):
    number = models.PositiveSmallIntegerField(unique=True)
    capacity = models.PositiveSmallIntegerField(default=4)
    qr_token = models.CharField(max_length=64, unique=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["number"]

    def __str__(self) -> str:
        return f"Table {self.number}"


class Order(models.Model):
    class Type(models.TextChoices):
        DINE_IN = "dine_in", "Dine-in"
        TAKEAWAY = "takeaway", "Takeaway"
        DELIVERY = "delivery", "Delivery"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PENDING = "pending", "Pending"
        CONFIRMED = "confirmed", "Confirmed"
        PREPARING = "preparing", "Preparing"
        READY = "ready", "Ready"
        SERVED = "served", "Served"
        CANCELLED = "cancelled", "Cancelled"

    class PaymentStatus(models.TextChoices):
        UNPAID = "unpaid", "Unpaid"
        PAID = "paid", "Paid"

    uuid = models.UUIDField(default=uuid_lib.uuid4, unique=True, editable=False, db_index=True)
    number = models.CharField(max_length=20, unique=True, blank=True)

    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="orders_as_customer",
        null=True,
        blank=True,
    )
    cashier = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="orders_as_cashier",
        null=True,
        blank=True,
    )
    table = models.ForeignKey(
        Table, on_delete=models.PROTECT, null=True, blank=True, related_name="orders"
    )

    order_type = models.CharField(max_length=10, choices=Type.choices)
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.DRAFT, db_index=True
    )
    payment_status = models.CharField(
        max_length=10, choices=PaymentStatus.choices, default=PaymentStatus.UNPAID
    )

    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0"))
    tax = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0"))
    service_charge = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0")
    )
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0"))
    total = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0"))

    delivery_address = models.TextField(blank=True)
    customer_phone = models.CharField(max_length=20, blank=True)
    notes = models.TextField(blank=True)

    snapshot = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    ready_at = models.DateTimeField(null=True, blank=True)
    served_at = models.DateTimeField(null=True, blank=True)

    objects = OrderManager()

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["customer", "-created_at"]),
        ]

    def __str__(self) -> str:
        return self.number or f"Order {self.uuid}"

    @staticmethod
    def next_number_for(today: date_cls | None = None) -> str:
        from django.utils.timezone import localdate

        today = today or localdate()
        seq = Order.objects.filter(created_at__date=today).count() + 1
        return f"{today:%Y%m%d}-{seq:04d}"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    menu_item = models.ForeignKey(
        "menu.MenuItem", on_delete=models.PROTECT, related_name="+"
    )
    quantity = models.PositiveSmallIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    notes = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["id"]

    def __str__(self) -> str:
        return f"{self.quantity}× {self.menu_item.name}"


class OrderItemModifier(models.Model):
    order_item = models.ForeignKey(
        OrderItem, on_delete=models.CASCADE, related_name="modifiers"
    )
    option = models.ForeignKey(
        "menu.ModifierOption", on_delete=models.PROTECT, related_name="+"
    )
    price_delta = models.DecimalField(max_digits=8, decimal_places=2)

    class Meta:
        ordering = ["id"]

    def __str__(self) -> str:
        return f"{self.option} (+{self.price_delta})"

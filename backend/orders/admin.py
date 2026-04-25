"""Django admin registrations for orders + tables."""
from django.contrib import admin

from .models import Order, OrderItem, OrderItemModifier, Table


class OrderItemModifierInline(admin.TabularInline):
    model = OrderItemModifier
    extra = 0
    readonly_fields = ("option", "price_delta")
    can_delete = False


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ("menu_item", "quantity", "unit_price", "notes")
    can_delete = False
    show_change_link = True


@admin.register(Table)
class TableAdmin(admin.ModelAdmin):
    list_display = ("number", "capacity", "is_active")
    list_filter = ("is_active",)
    search_fields = ("number",)


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "number", "order_type", "status", "payment_status",
        "total", "customer", "cashier", "created_at",
    )
    list_filter = ("status", "payment_status", "order_type")
    search_fields = ("number", "uuid", "customer__email", "cashier__email")
    readonly_fields = (
        "uuid", "number", "subtotal", "tax", "total",
        "snapshot", "created_at", "confirmed_at", "ready_at", "served_at",
    )
    inlines = [OrderItemInline]
    ordering = ("-created_at",)


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ("order", "menu_item", "quantity", "unit_price")
    search_fields = ("order__number", "menu_item__name")
    readonly_fields = ("order", "menu_item", "quantity", "unit_price", "notes")
    inlines = [OrderItemModifierInline]

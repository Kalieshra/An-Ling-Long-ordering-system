"""Cashier-side server-rendered views and JSON endpoints."""
import json

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.generic import TemplateView, View
from menu.models import Category, MenuItem

from .exceptions import InvalidTransition, OrderValidationError
from .models import Order, Table
from .services import confirm_order, create_order, mark_paid_cash


class _CashierMixin(LoginRequiredMixin):
    """Middleware enforces /cashier/ → cashier role; LoginRequired covers the unauthenticated redirect."""


class POSView(_CashierMixin, TemplateView):
    template_name = "cashier/home.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        items_qs = (
            MenuItem.objects.available()
            .select_related("category")
            .prefetch_related("modifier_groups__options")
        )
        items_data = []
        for it in items_qs:
            items_data.append({
                "id": it.id,
                "name": it.name,
                "price": str(it.price),
                "image_url": it.image.url if it.image else "",
                "category_slug": it.category.slug,
                "modifier_groups": [
                    {
                        "id": g.id,
                        "name": g.name,
                        "min_select": g.min_select,
                        "max_select": g.max_select,
                        "is_required": g.is_required,
                        "options": [
                            {"id": o.id, "name": o.name, "price_delta": str(o.price_delta)}
                            for o in g.options.filter(is_available=True)
                        ],
                    }
                    for g in it.modifier_groups.all()
                ],
            })
        cats = [
            {"id": c.id, "slug": c.slug, "name": c.name}
            for c in Category.objects.filter(is_active=True)
        ]
        ctx["pos_data"] = {"categories": cats, "items": items_data}
        ctx["tables"] = list(Table.objects.filter(is_active=True))
        ctx["tax_rate"] = "0.14"
        return ctx


class OrderCreateView(_CashierMixin, View):
    http_method_names = ["post"]

    def post(self, request):
        try:
            payload = json.loads(request.body or "{}")
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON."}, status=400)

        order_type = payload.get("type")
        items = payload.get("items", [])
        table_id = payload.get("table")
        delivery_address = (payload.get("delivery_address") or "").strip()
        customer_phone = (payload.get("customer_phone") or "").strip()
        notes = (payload.get("notes") or "").strip()

        table = None
        if order_type == Order.Type.DINE_IN:
            table = get_object_or_404(Table, pk=table_id, is_active=True) if table_id else None

        try:
            order = create_order(
                cart=items,
                cashier=request.user,
                table=table,
                order_type=order_type,
                delivery_address=delivery_address,
                customer_phone=customer_phone,
                notes=notes,
                initial_status=Order.Status.DRAFT,
            )
            confirm_order(order)
        except OrderValidationError as e:
            return JsonResponse({"error": str(e)}, status=400)

        return JsonResponse({
            "uuid": str(order.uuid),
            "number": order.number,
            "redirect": f"/cashier/orders/{order.uuid}/",
        })


class OrderDetailView(_CashierMixin, View):
    def get(self, request, uuid):
        order = get_object_or_404(
            Order.objects.prefetch_related("items__modifiers__option", "items__menu_item"),
            uuid=uuid,
        )
        return render(request, "cashier/order_detail.html", {"order": order})


class MarkPaidView(_CashierMixin, View):
    http_method_names = ["post"]

    def post(self, request, uuid):
        order = get_object_or_404(Order, uuid=uuid)
        try:
            mark_paid_cash(order, cashier=request.user)
        except InvalidTransition:
            pass  # already paid — idempotent UX
        return redirect("cashier:order-detail", uuid=order.uuid)


class ReceiptView(_CashierMixin, View):
    def get(self, request, uuid):
        order = get_object_or_404(Order, uuid=uuid)
        snapshot_items = order.snapshot.get("items", [])
        return render(request, "cashier/receipt.html", {
            "order": order,
            "snapshot_items": snapshot_items,
        })


class PendingListView(_CashierMixin, View):
    def get(self, request):
        pending = Order.objects.pending().order_by("created_at")
        return render(request, "cashier/pending_list.html", {"orders": pending})


class ConfirmPendingView(_CashierMixin, View):
    http_method_names = ["post"]

    def post(self, request, uuid):
        order = get_object_or_404(Order, uuid=uuid, status=Order.Status.PENDING)
        try:
            confirm_order(order)
        except InvalidTransition:
            pass
        return redirect("cashier:pending-list")

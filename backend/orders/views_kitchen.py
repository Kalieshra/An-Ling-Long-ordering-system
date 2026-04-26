"""Kitchen-side server-rendered list + status-transition POST."""
from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.views.generic import View

from .exceptions import InvalidTransition
from .models import Order
from .services import update_order_status


class _KitchenMixin(LoginRequiredMixin):
    """Middleware enforces /kitchen/ → kitchen role."""


class KitchenListView(_KitchenMixin, View):
    def get(self, request):
        from .services import _serialise_for_broadcast  # internal use OK
        orders = (
            Order.objects.kitchen_visible()
            .select_related("table", "customer")
            .prefetch_related("items__menu_item", "items__modifiers__option")
            .order_by("created_at")
        )
        initial_orders = [
            _serialise_for_broadcast(o) | {"created_at": o.created_at.isoformat()}
            for o in orders
        ]
        return render(request, "kitchen/home.html", {
            "initial_orders": initial_orders,
            "ws_base_url": settings.RMS_WS_BASE_URL,
        })


class KitchenStatusView(_KitchenMixin, View):
    http_method_names = ["post"]
    _NEXT_STATUS = {
        Order.Status.CONFIRMED: Order.Status.PREPARING,
        Order.Status.PREPARING: Order.Status.READY,
        Order.Status.READY: Order.Status.SERVED,
    }

    def post(self, request, uuid):
        order = get_object_or_404(Order, uuid=uuid)
        target = request.POST.get("status")
        expected = self._NEXT_STATUS.get(order.status)
        if expected is None or target != expected.value:
            return HttpResponseBadRequest(
                f"Cannot transition order {order.number} from {order.status} to {target!r}."
            )
        try:
            update_order_status(order, target, by_user=request.user)
        except InvalidTransition as e:
            return HttpResponseBadRequest(str(e))
        return redirect("kitchen:home")

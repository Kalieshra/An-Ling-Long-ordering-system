"""Kitchen-side server-rendered list + status-transition POST."""
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.views.generic import View

from .exceptions import InvalidTransition
from .models import Order
from .services import transition_status


class _KitchenMixin(LoginRequiredMixin):
    """Middleware enforces /kitchen/ → kitchen role."""


class KitchenListView(_KitchenMixin, View):
    def get(self, request):
        orders = (
            Order.objects.kitchen_visible()
            .select_related("table", "customer")
            .prefetch_related("items__menu_item", "items__modifiers__option")
            .order_by("created_at")
        )
        return render(request, "kitchen/home.html", {"orders": orders})


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
            transition_status(order, target, by_user=request.user)
        except InvalidTransition as e:
            return HttpResponseBadRequest(str(e))
        return redirect("kitchen:home")

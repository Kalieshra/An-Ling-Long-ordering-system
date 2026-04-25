"""Customer-facing JWT API for orders."""
from accounts.permissions import IsCustomer
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .exceptions import InvalidTransition
from .models import Order
from .serializers import (
    OrderCreateSerializer,
    OrderDetailSerializer,
    OrderListSerializer,
)
from .services import cancel_order


class OrderViewSet(viewsets.ModelViewSet):
    """Customer can list/retrieve/create their own orders, and cancel while still pending."""

    permission_classes = [IsAuthenticated, IsCustomer]
    lookup_field = "uuid"
    http_method_names = ["get", "post", "patch"]

    def get_queryset(self):
        qs = Order.objects.for_customer(self.request.user)
        if self.action in ("retrieve", "cancel"):
            qs = qs.prefetch_related("items__modifiers__option", "items__menu_item")
        return qs

    def get_serializer_class(self):
        if self.action == "create":
            return OrderCreateSerializer
        if self.action == "list":
            return OrderListSerializer
        return OrderDetailSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order = serializer.save()
        out = OrderDetailSerializer(order, context={"request": request})
        return Response(out.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["patch"])
    def cancel(self, request, uuid=None):
        order = self.get_object()
        try:
            cancel_order(order)
        except InvalidTransition as e:
            return Response({"detail": str(e)}, status=status.HTTP_409_CONFLICT)
        return Response(OrderDetailSerializer(order).data)

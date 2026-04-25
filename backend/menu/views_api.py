"""Public read-only menu API."""
from rest_framework import generics, viewsets
from rest_framework.permissions import AllowAny

from .filters import MenuItemFilter
from .models import Category, MenuItem
from .serializers import (
    CategorySerializer,
    MenuItemDetailSerializer,
    MenuItemListSerializer,
)


class CategoryListView(generics.ListAPIView):
    queryset = Category.objects.filter(is_active=True)
    serializer_class = CategorySerializer
    permission_classes = [AllowAny]
    authentication_classes = []
    filter_backends = []
    pagination_class = None  # categories list is small, return flat list


class MenuItemViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = MenuItemListSerializer
    permission_classes = [AllowAny]
    authentication_classes = []
    filterset_class = MenuItemFilter
    ordering_fields = ["name", "price"]

    def get_queryset(self):
        qs = MenuItem.objects.available().select_related("category")
        if self.action == "retrieve":
            qs = qs.prefetch_related("modifier_groups__options")
        return qs

    def get_serializer_class(self):
        if self.action == "retrieve":
            return MenuItemDetailSerializer
        return MenuItemListSerializer

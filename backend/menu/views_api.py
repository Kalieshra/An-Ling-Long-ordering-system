"""Public read-only menu API."""
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.views.decorators.vary import vary_on_headers
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


@method_decorator(cache_page(60), name="dispatch")
@method_decorator(vary_on_headers("Accept-Language"), name="dispatch")
class FeaturedMenuView(generics.ListAPIView):
    """Items whose `tags` JSONB contains 'featured'. Cached 60s.

    Anonymous-accessible; cache key is per (path, query, language).
    """

    serializer_class = MenuItemListSerializer
    permission_classes = [AllowAny]
    authentication_classes = []
    pagination_class = None

    def get_queryset(self):
        return (
            MenuItem.objects.available()
            .filter(tags__contains=["featured"])
            .select_related("category")
            .order_by("name")
        )

    def list(self, request, *args, **kwargs):
        from rest_framework.response import Response

        qs = self.get_queryset()
        data = self.get_serializer(qs, many=True).data
        return Response({"results": data})

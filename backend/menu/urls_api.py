"""URL routes for /api/v1/menu/."""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views_api import CategoryListView, FeaturedMenuView, MenuItemViewSet

router = DefaultRouter()
router.register("items", MenuItemViewSet, basename="menu-items")

urlpatterns = [
    path("categories/", CategoryListView.as_view(), name="menu-categories"),
    path("featured/", FeaturedMenuView.as_view(), name="menu-featured"),
    path("", include(router.urls)),
]

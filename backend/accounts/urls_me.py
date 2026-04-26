"""URLs for /api/v1/me/."""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views_api import MeView, SavedAddressViewSet

router = DefaultRouter()
router.register("addresses", SavedAddressViewSet, basename="me-address")

urlpatterns = [
    path("", MeView.as_view(), name="me-profile"),
    path("", include(router.urls)),
]

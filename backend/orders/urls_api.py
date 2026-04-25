"""URLs for /api/v1/orders/."""
from rest_framework.routers import DefaultRouter

from .views_api import OrderViewSet

router = DefaultRouter()
router.register("", OrderViewSet, basename="orders")

urlpatterns = router.urls

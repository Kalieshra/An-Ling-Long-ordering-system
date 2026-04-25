"""URLs for /kitchen/."""
from django.urls import path

from . import views_kitchen as v

app_name = "kitchen"

urlpatterns = [
    path("", v.KitchenListView.as_view(), name="home"),
    path("orders/<uuid:uuid>/status/", v.KitchenStatusView.as_view(), name="order-status"),
]

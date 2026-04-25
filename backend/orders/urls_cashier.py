"""URLs for /cashier/."""
from django.urls import path

from . import views_cashier as v

app_name = "cashier"

urlpatterns = [
    path("", v.POSView.as_view(), name="home"),
    path("orders/create/", v.OrderCreateView.as_view(), name="order-create"),
]

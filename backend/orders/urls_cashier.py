"""URLs for /cashier/."""
from django.urls import path

from . import views_cashier as v

app_name = "cashier"

urlpatterns = [
    path("", v.POSView.as_view(), name="home"),
    path("orders/create/", v.OrderCreateView.as_view(), name="order-create"),
    path("orders/<uuid:uuid>/", v.OrderDetailView.as_view(), name="order-detail"),
    path("orders/<uuid:uuid>/mark-paid/", v.MarkPaidView.as_view(), name="order-mark-paid"),
    path("orders/<uuid:uuid>/receipt/", v.ReceiptView.as_view(), name="order-receipt"),
]

"""Web routes (session auth)."""
from django.urls import path

from . import views_web

urlpatterns = [
    path("login/", views_web.staff_login, name="staff-login"),
    path("logout/", views_web.staff_logout, name="staff-logout"),
    path("dashboard/", views_web.dashboard_home, name="dashboard-home"),
    path("cashier/", views_web.cashier_home, name="cashier-home"),
    path("kitchen/", views_web.kitchen_home, name="kitchen-home"),
]

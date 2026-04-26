"""URLs for /api/v1/me/."""
from django.urls import path

from .views_api import MeView

urlpatterns = [
    path("", MeView.as_view(), name="me-profile"),
]

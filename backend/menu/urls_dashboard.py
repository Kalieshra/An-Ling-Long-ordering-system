"""URL routes for /dashboard/menu/."""
from django.urls import path

from . import views_dashboard as v

app_name = "menu"

urlpatterns = [
    path("categories/", v.CategoryListView.as_view(), name="category-list"),
    path("categories/new/", v.CategoryCreateView.as_view(), name="category-new"),
    path("categories/<int:pk>/edit/", v.CategoryUpdateView.as_view(), name="category-edit"),
    path("categories/<int:pk>/delete/", v.CategoryDeleteView.as_view(), name="category-delete"),
]

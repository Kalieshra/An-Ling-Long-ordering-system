"""URL routes for /dashboard/menu/."""
from django.urls import path

from . import views_dashboard as v

app_name = "menu"

urlpatterns = [
    path("categories/", v.CategoryListView.as_view(), name="category-list"),
    path("categories/new/", v.CategoryCreateView.as_view(), name="category-new"),
    path("categories/<int:pk>/edit/", v.CategoryUpdateView.as_view(), name="category-edit"),
    path("categories/<int:pk>/delete/", v.CategoryDeleteView.as_view(), name="category-delete"),
    # Menu items
    path("items/", v.MenuItemListView.as_view(), name="menuitem-list"),
    path("items/new/", v.MenuItemCreateView.as_view(), name="menuitem-new"),
    path("items/<int:pk>/edit/", v.MenuItemUpdateView.as_view(), name="menuitem-edit"),
    path("items/<int:pk>/toggle/", v.MenuItemToggleAvailableView.as_view(), name="menuitem-toggle"),
    path("items/<int:pk>/delete/", v.MenuItemDeleteView.as_view(), name="menuitem-delete"),
    # Inventory
    path("inventory/", v.IngredientListView.as_view(), name="ingredient-list"),
    path("inventory/new/", v.IngredientCreateView.as_view(), name="ingredient-new"),
    path("inventory/<int:pk>/edit/", v.IngredientUpdateView.as_view(), name="ingredient-edit"),
    path("inventory/<int:pk>/delete/", v.IngredientDeleteView.as_view(), name="ingredient-delete"),
]

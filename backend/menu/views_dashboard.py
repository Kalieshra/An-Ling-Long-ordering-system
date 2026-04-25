"""Class-based views for the admin dashboard CRUD UI."""
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.generic import (
    CreateView,
    DeleteView,
    ListView,
    UpdateView,
    View,
)

from .forms import CategoryForm, IngredientForm, MenuItemForm, ModifierGroupFormSet
from .models import Category, Ingredient, MenuItem


class _DashboardMixin(LoginRequiredMixin):
    """Base for all dashboard views — middleware enforces ADMIN role on /dashboard/."""


class CategoryListView(_DashboardMixin, ListView):
    model = Category
    template_name = "dashboard/categories/list.html"
    context_object_name = "categories"
    paginate_by = 50


class CategoryCreateView(_DashboardMixin, CreateView):
    model = Category
    form_class = CategoryForm
    template_name = "dashboard/categories/form.html"
    success_url = reverse_lazy("menu:category-list")


class CategoryUpdateView(_DashboardMixin, UpdateView):
    model = Category
    form_class = CategoryForm
    template_name = "dashboard/categories/form.html"
    success_url = reverse_lazy("menu:category-list")


class CategoryDeleteView(_DashboardMixin, DeleteView):
    model = Category
    template_name = "dashboard/categories/confirm_delete.html"
    success_url = reverse_lazy("menu:category-list")


class MenuItemListView(_DashboardMixin, ListView):
    model = MenuItem
    template_name = "dashboard/menu/list.html"
    context_object_name = "items"
    paginate_by = 50

    def get_queryset(self):
        return MenuItem.objects.select_related("category").all()


class _MenuItemFormMixin:
    """Shared logic for create + update views with the modifier-groups formset."""

    template_name = "dashboard/menu/form.html"
    form_class = MenuItemForm
    success_url = reverse_lazy("menu:menuitem-list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        if self.request.POST:
            ctx["groups_formset"] = ModifierGroupFormSet(
                self.request.POST, instance=self.object
            )
        else:
            ctx["groups_formset"] = ModifierGroupFormSet(instance=self.object)
        return ctx

    def form_valid(self, form):
        with transaction.atomic():
            self.object = form.save()
            groups_formset = ModifierGroupFormSet(self.request.POST, instance=self.object)
            if groups_formset.is_valid():
                groups_formset.save()
            else:
                return self.form_invalid(form)
        return HttpResponseRedirect(self.get_success_url())


class MenuItemCreateView(_DashboardMixin, _MenuItemFormMixin, CreateView):
    model = MenuItem


class MenuItemUpdateView(_DashboardMixin, _MenuItemFormMixin, UpdateView):
    model = MenuItem


class MenuItemDeleteView(_DashboardMixin, DeleteView):
    model = MenuItem
    template_name = "dashboard/menu/confirm_delete.html"
    success_url = reverse_lazy("menu:menuitem-list")


class MenuItemToggleAvailableView(_DashboardMixin, View):
    http_method_names = ["post"]

    def post(self, request, pk):
        item = get_object_or_404(MenuItem, pk=pk)
        item.is_available = not item.is_available
        item.save(update_fields=["is_available"])
        return redirect("menu:menuitem-list")


class IngredientListView(_DashboardMixin, ListView):
    model = Ingredient
    template_name = "dashboard/inventory/list.html"
    context_object_name = "ingredients"
    paginate_by = 50


class IngredientCreateView(_DashboardMixin, CreateView):
    model = Ingredient
    form_class = IngredientForm
    template_name = "dashboard/inventory/form.html"
    success_url = reverse_lazy("menu:ingredient-list")


class IngredientUpdateView(_DashboardMixin, UpdateView):
    model = Ingredient
    form_class = IngredientForm
    template_name = "dashboard/inventory/form.html"
    success_url = reverse_lazy("menu:ingredient-list")


class IngredientDeleteView(_DashboardMixin, DeleteView):
    model = Ingredient
    template_name = "dashboard/inventory/confirm_delete.html"
    success_url = reverse_lazy("menu:ingredient-list")

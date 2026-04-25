"""Class-based views for the admin dashboard CRUD UI."""
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import (
    CreateView,
    DeleteView,
    ListView,
    UpdateView,
)

from .forms import CategoryForm
from .models import Category


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

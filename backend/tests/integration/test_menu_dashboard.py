"""Integration tests for the dashboard CRUD UI (category section)."""
import pytest
from accounts.models import Role, User
from django.test import Client
from menu.models import Category


@pytest.fixture
def admin_client(db):
    user = User.objects.create_user(
        email="admin@x.com", password="pw-long-enough", role=Role.ADMIN
    )
    c = Client()
    c.force_login(user)
    return c


@pytest.fixture
def cashier_client(db):
    user = User.objects.create_user(
        email="cashier@x.com", password="pw-long-enough", role=Role.CASHIER
    )
    c = Client()
    c.force_login(user)
    return c


@pytest.mark.django_db
class TestCategoryCRUD:
    def test_admin_can_list(self, admin_client):
        Category.objects.create(name="Pizzas", slug="pizzas")
        resp = admin_client.get("/dashboard/menu/categories/")
        assert resp.status_code == 200
        assert b"Pizzas" in resp.content

    def test_admin_can_create(self, admin_client):
        resp = admin_client.post(
            "/dashboard/menu/categories/new/",
            {"name": "Drinks", "slug": "drinks", "display_order": 0, "is_active": "on"},
        )
        assert resp.status_code == 302
        assert Category.objects.filter(slug="drinks").exists()

    def test_admin_can_edit(self, admin_client):
        cat = Category.objects.create(name="Old", slug="old")
        resp = admin_client.post(
            f"/dashboard/menu/categories/{cat.pk}/edit/",
            {"name": "New", "slug": "old", "display_order": 5, "is_active": "on"},
        )
        assert resp.status_code == 302
        cat.refresh_from_db()
        assert cat.name == "New"
        assert cat.display_order == 5

    def test_admin_can_delete_empty_category(self, admin_client):
        cat = Category.objects.create(name="Tmp", slug="tmp")
        resp = admin_client.post(f"/dashboard/menu/categories/{cat.pk}/delete/")
        assert resp.status_code == 302
        assert not Category.objects.filter(pk=cat.pk).exists()

    def test_cashier_blocked_from_category_list(self, cashier_client):
        resp = cashier_client.get("/dashboard/menu/categories/")
        assert resp.status_code == 403

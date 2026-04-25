"""Integration tests for the dashboard CRUD UI (category section)."""
from decimal import Decimal

import pytest
from accounts.models import Role, User
from django.test import Client
from menu.models import Category, MenuItem


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


@pytest.mark.django_db
class TestMenuItemCRUD:
    def _category(self):
        return Category.objects.create(name="Pizzas", slug="pizzas")

    def test_admin_can_list(self, admin_client):
        cat = self._category()
        MenuItem.objects.create(category=cat, name="Margherita", price=Decimal("85"))
        resp = admin_client.get("/dashboard/menu/items/")
        assert resp.status_code == 200
        assert b"Margherita" in resp.content

    def test_admin_can_create_with_modifier_group(self, admin_client):
        cat = self._category()
        resp = admin_client.post(
            "/dashboard/menu/items/new/",
            {
                "category": cat.pk, "name": "Margherita",
                "name_ar": "", "description": "",
                "item_type": "dish", "price": "85.00", "cost": "0",
                "is_available": "on", "prep_time_min": 10, "tags": "[]",
                # formset management form
                "modifier_groups-TOTAL_FORMS": "1",
                "modifier_groups-INITIAL_FORMS": "0",
                "modifier_groups-MIN_NUM_FORMS": "0",
                "modifier_groups-MAX_NUM_FORMS": "1000",
                "modifier_groups-0-name": "Size",
                "modifier_groups-0-min_select": "1",
                "modifier_groups-0-max_select": "1",
                "modifier_groups-0-is_required": "on",
                "modifier_groups-0-display_order": "0",
            },
        )
        assert resp.status_code == 302, resp.content
        item = MenuItem.objects.get(name="Margherita")
        assert item.modifier_groups.count() == 1
        assert item.modifier_groups.first().name == "Size"

    def test_admin_can_toggle_available(self, admin_client):
        cat = self._category()
        item = MenuItem.objects.create(category=cat, name="X", price=Decimal("1"))
        assert item.is_available is True
        resp = admin_client.post(f"/dashboard/menu/items/{item.pk}/toggle/")
        assert resp.status_code == 302
        item.refresh_from_db()
        assert item.is_available is False

    def test_admin_can_delete(self, admin_client):
        cat = self._category()
        item = MenuItem.objects.create(category=cat, name="X", price=Decimal("1"))
        resp = admin_client.post(f"/dashboard/menu/items/{item.pk}/delete/")
        assert resp.status_code == 302
        assert not MenuItem.objects.filter(pk=item.pk).exists()

    def test_cashier_blocked_from_items(self, cashier_client):
        resp = cashier_client.get("/dashboard/menu/items/")
        assert resp.status_code == 403

    def test_kitchen_blocked_from_new_item(self, db):
        user = User.objects.create_user(
            email="k@x.com", password="pw-long-enough", role=Role.KITCHEN
        )
        c = Client()
        c.force_login(user)
        resp = c.get("/dashboard/menu/items/new/")
        assert resp.status_code == 403

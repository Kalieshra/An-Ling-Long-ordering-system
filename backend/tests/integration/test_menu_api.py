"""Integration tests for /api/v1/menu/ endpoints."""
from decimal import Decimal

import pytest
from menu.models import Category, MenuItem, ModifierGroup, ModifierOption
from rest_framework.test import APIClient


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def pizzas(db):
    return Category.objects.create(name="Pizzas", slug="pizzas")


@pytest.fixture
def drinks(db):
    return Category.objects.create(name="Drinks", slug="drinks")


@pytest.fixture
def margherita(db, pizzas):
    item = MenuItem.objects.create(
        category=pizzas, name="Margherita Pizza", price=Decimal("85.00")
    )
    group = ModifierGroup.objects.create(menu_item=item, name="Size", is_required=True)
    ModifierOption.objects.create(group=group, name="Small", price_delta=Decimal("0"))
    ModifierOption.objects.create(group=group, name="Large", price_delta=Decimal("30"))
    return item


@pytest.mark.django_db
class TestCategoriesEndpoint:
    url = "/api/v1/menu/categories/"

    def test_lists_active_categories(self, client, pizzas, drinks):
        Category.objects.create(name="Hidden", slug="hidden", is_active=False)
        resp = client.get(self.url)
        assert resp.status_code == 200
        # CategoryListView has pagination_class=None so response is a flat list
        slugs = [c["slug"] for c in resp.data]
        assert "pizzas" in slugs
        assert "drinks" in slugs
        assert "hidden" not in slugs

    def test_anonymous_access_allowed(self, client):
        resp = client.get(self.url)
        assert resp.status_code == 200


@pytest.mark.django_db
class TestMenuItemsListEndpoint:
    url = "/api/v1/menu/items/"

    def test_returns_only_available_items(self, client, pizzas, margherita):
        MenuItem.objects.create(
            category=pizzas, name="Hidden Pie", price=Decimal("1"), is_available=False
        )
        resp = client.get(self.url)
        assert resp.status_code == 200
        names = [i["name"] for i in resp.data["results"]]
        assert "Margherita Pizza" in names
        assert "Hidden Pie" not in names

    def test_filter_by_category_slug(self, client, pizzas, drinks, margherita):
        MenuItem.objects.create(category=drinks, name="Cola", price=Decimal("15"))
        resp = client.get(self.url + "?category=drinks")
        names = [i["name"] for i in resp.data["results"]]
        assert names == ["Cola"]

    def test_filter_by_type(self, client, pizzas, margherita):
        MenuItem.objects.create(
            category=pizzas, name="Cola Bottle", price=Decimal("15"),
            item_type=MenuItem.Type.DRINK,
        )
        resp = client.get(self.url + "?type=drink")
        names = [i["name"] for i in resp.data["results"]]
        assert names == ["Cola Bottle"]

    def test_search_fuzzy(self, client, pizzas, margherita):
        resp = client.get(self.url + "?search=marg")
        assert resp.status_code == 200
        names = [i["name"] for i in resp.data["results"]]
        assert "Margherita Pizza" in names

    def test_ordering_by_price(self, client, pizzas):
        MenuItem.objects.create(category=pizzas, name="Cheap", price=Decimal("10"))
        MenuItem.objects.create(category=pizzas, name="Expensive", price=Decimal("200"))
        resp = client.get(self.url + "?ordering=price")
        names = [i["name"] for i in resp.data["results"]]
        assert names.index("Cheap") < names.index("Expensive")

    def test_pagination_present(self, client, pizzas):
        for i in range(25):
            MenuItem.objects.create(category=pizzas, name=f"Item{i:02d}", price=Decimal("1"))
        resp = client.get(self.url)
        assert "count" in resp.data
        assert "next" in resp.data
        assert resp.data["count"] >= 25


@pytest.mark.django_db
class TestMenuItemDetailEndpoint:
    def test_returns_nested_modifier_groups(self, client, margherita):
        resp = client.get(f"/api/v1/menu/items/{margherita.id}/")
        assert resp.status_code == 200
        assert resp.data["name"] == "Margherita Pizza"
        groups = resp.data["modifier_groups"]
        assert len(groups) == 1
        assert groups[0]["name"] == "Size"
        opts = groups[0]["options"]
        assert {o["name"] for o in opts} == {"Small", "Large"}

    def test_404_on_unknown_id(self, client):
        resp = client.get("/api/v1/menu/items/99999/")
        assert resp.status_code == 404

    def test_404_on_unavailable_item(self, client, pizzas):
        item = MenuItem.objects.create(
            category=pizzas, name="Hidden", price=Decimal("1"), is_available=False
        )
        resp = client.get(f"/api/v1/menu/items/{item.id}/")
        assert resp.status_code == 404

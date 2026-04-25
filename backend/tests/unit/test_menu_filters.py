"""Unit tests for MenuItemFilter behavior."""
from decimal import Decimal

import pytest
from menu.filters import MenuItemFilter
from menu.models import Category, MenuItem


@pytest.fixture
def setup(db):
    cat_pizza = Category.objects.create(name="Pizzas", slug="pizzas")
    cat_drink = Category.objects.create(name="Drinks", slug="drinks")
    items = {
        "marg": MenuItem.objects.create(
            category=cat_pizza, name="Margherita", price=Decimal("85"),
        ),
        "burger": MenuItem.objects.create(
            category=cat_pizza, name="Burger", price=Decimal("120"),
        ),
        "cola": MenuItem.objects.create(
            category=cat_drink, name="Cola", price=Decimal("15"),
            item_type=MenuItem.Type.DRINK,
        ),
    }
    return items


@pytest.mark.django_db
def test_filter_by_category_slug(setup):
    f = MenuItemFilter({"category": "drinks"}, queryset=MenuItem.objects.available())
    names = list(f.qs.values_list("name", flat=True))
    assert names == ["Cola"]


@pytest.mark.django_db
def test_filter_by_type(setup):
    f = MenuItemFilter({"type": "drink"}, queryset=MenuItem.objects.available())
    names = list(f.qs.values_list("name", flat=True))
    assert names == ["Cola"]


@pytest.mark.django_db
def test_search_fuzzy_match(setup):
    f = MenuItemFilter({"search": "marg"}, queryset=MenuItem.objects.available())
    names = list(f.qs.values_list("name", flat=True))
    assert "Margherita" in names


@pytest.mark.django_db
def test_search_typo_fuzzy(setup):
    f = MenuItemFilter({"search": "burgr"}, queryset=MenuItem.objects.available())
    names = list(f.qs.values_list("name", flat=True))
    assert "Burger" in names


@pytest.mark.django_db
def test_search_empty_returns_all(setup):
    f = MenuItemFilter({"search": ""}, queryset=MenuItem.objects.available())
    assert f.qs.count() == 3

"""Unit tests for menu app models."""
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from menu.models import (
    Category,
    Ingredient,
    MenuItem,
    ModifierGroup,
    ModifierOption,
    Recipe,
)


@pytest.fixture
def category(db):
    return Category.objects.create(name="Pizzas", slug="pizzas")


@pytest.fixture
def margherita(db, category):
    return MenuItem.objects.create(
        category=category, name="Margherita", price=Decimal("85.00")
    )


@pytest.mark.django_db
class TestCategory:
    def test_creates_with_required_fields(self, category):
        assert category.is_active is True
        assert category.display_order == 0
        assert str(category) == "Pizzas"

    def test_slug_must_be_unique(self):
        Category.objects.create(name="A", slug="dup")
        with pytest.raises(IntegrityError):
            Category.objects.create(name="B", slug="dup")

    def test_default_ordering_is_display_order_then_name(self):
        Category.objects.create(name="Beta", slug="b", display_order=2)
        Category.objects.create(name="Alpha", slug="a", display_order=1)
        Category.objects.create(name="Gamma", slug="g", display_order=1)
        slugs = list(Category.objects.values_list("slug", flat=True))
        assert slugs == ["a", "g", "b"]


@pytest.mark.django_db
class TestMenuItem:
    def test_default_type_is_dish(self, margherita):
        assert margherita.item_type == MenuItem.Type.DISH

    def test_negative_price_rejected(self, category):
        item = MenuItem(category=category, name="Bad", price=Decimal("-1.00"))
        with pytest.raises(ValidationError):
            item.full_clean()

    def test_str_returns_name(self, margherita):
        assert str(margherita) == "Margherita"

    def test_available_manager_excludes_unavailable(self, margherita, category):
        unavail = MenuItem.objects.create(
            category=category, name="Hidden", price=Decimal("1.00"), is_available=False
        )
        avail = list(MenuItem.objects.available().values_list("id", flat=True))
        assert margherita.id in avail
        assert unavail.id not in avail

    def test_available_manager_excludes_items_in_inactive_category(self, category):
        inactive = Category.objects.create(name="Hidden", slug="hidden", is_active=False)
        MenuItem.objects.create(category=inactive, name="HiddenDish", price=Decimal("1"))
        avail_names = list(MenuItem.objects.available().values_list("name", flat=True))
        assert "HiddenDish" not in avail_names

    def test_tags_default_empty_list(self, margherita):
        assert margherita.tags == []


@pytest.mark.django_db
class TestModifierGroupAndOption:
    def test_group_cascade_deletes_options(self, margherita):
        group = ModifierGroup.objects.create(menu_item=margherita, name="Size")
        ModifierOption.objects.create(group=group, name="Small")
        ModifierOption.objects.create(group=group, name="Large")
        assert ModifierOption.objects.count() == 2
        group.delete()
        assert ModifierOption.objects.count() == 0

    def test_option_ordering_by_display_order(self, margherita):
        group = ModifierGroup.objects.create(menu_item=margherita, name="Size")
        ModifierOption.objects.create(group=group, name="L", display_order=2)
        ModifierOption.objects.create(group=group, name="S", display_order=1)
        names = list(group.options.values_list("name", flat=True))
        assert names == ["S", "L"]


@pytest.mark.django_db
class TestIngredient:
    def test_is_low_when_stock_below_threshold(self):
        ing = Ingredient.objects.create(
            name="Tomato", unit=Ingredient.Unit.KG,
            stock_qty=Decimal("0.5"), low_threshold=Decimal("1.0"),
        )
        assert ing.is_low is True

    def test_is_not_low_when_above_threshold(self):
        ing = Ingredient.objects.create(
            name="Cheese", unit=Ingredient.Unit.KG,
            stock_qty=Decimal("5.0"), low_threshold=Decimal("1.0"),
        )
        assert ing.is_low is False

    def test_name_unique(self):
        Ingredient.objects.create(name="Salt", unit=Ingredient.Unit.GRAM)
        with pytest.raises(IntegrityError):
            Ingredient.objects.create(name="Salt", unit=Ingredient.Unit.KG)


@pytest.mark.django_db
class TestRecipe:
    def test_unique_per_menu_item_and_ingredient(self, margherita):
        ing = Ingredient.objects.create(name="Cheese", unit=Ingredient.Unit.KG)
        Recipe.objects.create(menu_item=margherita, ingredient=ing, quantity=Decimal("0.2"))
        with pytest.raises(IntegrityError):
            Recipe.objects.create(menu_item=margherita, ingredient=ing, quantity=Decimal("0.3"))

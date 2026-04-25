"""Menu models — categories, items, modifiers, ingredients, recipes."""
from decimal import Decimal

from django.contrib.postgres.indexes import GinIndex
from django.core.validators import MinValueValidator
from django.db import models

from .managers import MenuItemManager


class Category(models.Model):
    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to="categories/", blank=True, null=True)
    display_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["display_order", "name"]

    def __str__(self) -> str:
        return self.name


class MenuItem(models.Model):
    class Type(models.TextChoices):
        DISH = "dish", "Dish"
        DRINK = "drink", "Drink"
        COMBO = "combo", "Combo"

    category = models.ForeignKey(
        Category, on_delete=models.PROTECT, related_name="items"
    )
    name = models.CharField(max_length=120)
    name_ar = models.CharField(max_length=120, blank=True)
    description = models.TextField(blank=True)
    item_type = models.CharField(
        max_length=10, choices=Type.choices, default=Type.DISH
    )
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0"))],
    )
    cost = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0"))
    image = models.ImageField(upload_to="menu/", blank=True, null=True)
    is_available = models.BooleanField(default=True, db_index=True)
    prep_time_min = models.PositiveSmallIntegerField(default=10)
    calories = models.PositiveIntegerField(null=True, blank=True)
    tags = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = MenuItemManager()

    class Meta:
        indexes = [
            models.Index(fields=["category", "is_available"]),
            models.Index(fields=["item_type", "is_available"]),
            GinIndex(
                fields=["name"],
                name="menuitem_name_trgm_idx",
                opclasses=["gin_trgm_ops"],
            ),
        ]
        ordering = ["category__display_order", "name"]

    def __str__(self) -> str:
        return self.name


class ModifierGroup(models.Model):
    menu_item = models.ForeignKey(
        MenuItem, on_delete=models.CASCADE, related_name="modifier_groups"
    )
    name = models.CharField(max_length=80)
    min_select = models.PositiveSmallIntegerField(default=0)
    max_select = models.PositiveSmallIntegerField(default=1)
    is_required = models.BooleanField(default=False)
    display_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["display_order"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(max_select__gte=models.F("min_select")),
                name="modifiergroup_max_gte_min",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.menu_item.name} — {self.name}"


class ModifierOption(models.Model):
    group = models.ForeignKey(
        ModifierGroup, on_delete=models.CASCADE, related_name="options"
    )
    name = models.CharField(max_length=80)
    price_delta = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("0"))
    is_available = models.BooleanField(default=True)
    display_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["display_order"]

    def __str__(self) -> str:
        return self.name


class Ingredient(models.Model):
    class Unit(models.TextChoices):
        GRAM = "g", "Grams"
        KG = "kg", "Kilograms"
        ML = "ml", "Milliliters"
        L = "l", "Liters"
        PIECE = "pc", "Piece"

    name = models.CharField(max_length=100, unique=True)
    unit = models.CharField(max_length=4, choices=Unit.choices)
    stock_qty = models.DecimalField(max_digits=12, decimal_places=3, default=Decimal("0"))
    low_threshold = models.DecimalField(
        max_digits=12, decimal_places=3, default=Decimal("0")
    )
    cost_per_unit = models.DecimalField(
        max_digits=10, decimal_places=4, default=Decimal("0")
    )
    supplier = models.CharField(max_length=120, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    @property
    def is_low(self) -> bool:
        # Opt-in: only flag when an operator has set a positive threshold,
        # otherwise an unconfigured ingredient (default threshold=0) would
        # always show as low.
        return self.low_threshold > 0 and self.stock_qty <= self.low_threshold


class Recipe(models.Model):
    menu_item = models.ForeignKey(
        MenuItem, on_delete=models.CASCADE, related_name="recipe_items"
    )
    ingredient = models.ForeignKey(
        Ingredient, on_delete=models.PROTECT, related_name="used_in"
    )
    quantity = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        validators=[MinValueValidator(Decimal("0.001"))],
    )

    class Meta:
        unique_together = [("menu_item", "ingredient")]
        ordering = ["ingredient__name"]

    def __str__(self) -> str:
        return f"{self.menu_item.name} ↔ {self.ingredient.name}"

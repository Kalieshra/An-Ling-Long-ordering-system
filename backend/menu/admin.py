"""Django admin registrations for menu models with inline editing."""
from django.contrib import admin

from .models import Category, Ingredient, MenuItem, ModifierGroup, ModifierOption, Recipe


class ModifierOptionInline(admin.TabularInline):
    model = ModifierOption
    extra = 1


class ModifierGroupInline(admin.TabularInline):
    model = ModifierGroup
    extra = 0
    show_change_link = True


class RecipeInline(admin.TabularInline):
    model = Recipe
    extra = 1
    autocomplete_fields = ["ingredient"]


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "display_order", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    ordering = ("display_order", "name")


@admin.register(MenuItem)
class MenuItemAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "item_type", "price", "is_available", "updated_at")
    list_filter = ("category", "item_type", "is_available")
    search_fields = ("name", "name_ar")
    list_editable = ("is_available",)
    inlines = [ModifierGroupInline, RecipeInline]
    ordering = ("category__display_order", "name")


@admin.register(ModifierGroup)
class ModifierGroupAdmin(admin.ModelAdmin):
    list_display = ("name", "menu_item", "min_select", "max_select", "is_required")
    list_filter = ("is_required",)
    search_fields = ("name", "menu_item__name")
    inlines = [ModifierOptionInline]


@admin.register(Ingredient)
class IngredientAdmin(admin.ModelAdmin):
    list_display = ("name", "unit", "stock_qty", "low_threshold", "is_low_display", "supplier")
    list_filter = ("unit",)
    search_fields = ("name", "supplier")

    @admin.display(boolean=True, description="Low?")
    def is_low_display(self, obj):
        return obj.is_low


@admin.register(Recipe)
class RecipeAdmin(admin.ModelAdmin):
    list_display = ("menu_item", "ingredient", "quantity")
    autocomplete_fields = ("menu_item", "ingredient")

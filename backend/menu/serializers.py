"""DRF serializers for the public menu API."""
from rest_framework import serializers

from .models import Category, MenuItem, ModifierGroup, ModifierOption


class CategorySerializer(serializers.ModelSerializer):
    image_url = serializers.ImageField(source="image", read_only=True)

    class Meta:
        model = Category
        fields = ("id", "name", "slug", "description", "image_url", "display_order")


class CategoryMiniSerializer(serializers.ModelSerializer):
    """Compact category embedded inside MenuItem responses."""

    class Meta:
        model = Category
        fields = ("id", "slug", "name")


class ModifierOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ModifierOption
        fields = ("id", "name", "price_delta", "is_available", "display_order")


class ModifierGroupSerializer(serializers.ModelSerializer):
    options = ModifierOptionSerializer(many=True, read_only=True)

    class Meta:
        model = ModifierGroup
        fields = (
            "id", "name", "min_select", "max_select", "is_required",
            "display_order", "options",
        )


class MenuItemListSerializer(serializers.ModelSerializer):
    category = CategoryMiniSerializer(read_only=True)
    image_url = serializers.ImageField(source="image", read_only=True)

    class Meta:
        model = MenuItem
        fields = (
            "id", "name", "name_ar", "item_type", "price",
            "image_url", "prep_time_min", "calories", "tags", "category",
        )


class MenuItemDetailSerializer(MenuItemListSerializer):
    description = serializers.CharField(read_only=True)
    modifier_groups = ModifierGroupSerializer(many=True, read_only=True)

    class Meta(MenuItemListSerializer.Meta):
        fields = MenuItemListSerializer.Meta.fields + (
            "description", "modifier_groups",
        )

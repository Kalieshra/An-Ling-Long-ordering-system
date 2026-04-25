"""Forms for the dashboard CRUD UI. Image-size validation lives here."""
from django import forms

from .models import Category, Ingredient, MenuItem, ModifierGroup, ModifierOption

MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB


def _check_image_size(image):
    if image and hasattr(image, "size") and image.size > MAX_UPLOAD_BYTES:
        raise forms.ValidationError(
            f"Image is {image.size // 1024} KB; max is {MAX_UPLOAD_BYTES // 1024} KB."
        )
    return image


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ["name", "slug", "description", "image", "display_order", "is_active"]

    def clean_image(self):
        return _check_image_size(self.cleaned_data.get("image"))


class MenuItemForm(forms.ModelForm):
    class Meta:
        model = MenuItem
        fields = [
            "category", "name", "name_ar", "description",
            "item_type", "price", "cost", "image",
            "is_available", "prep_time_min", "calories", "tags",
        ]

    def clean_image(self):
        return _check_image_size(self.cleaned_data.get("image"))


class IngredientForm(forms.ModelForm):
    class Meta:
        model = Ingredient
        fields = ["name", "unit", "stock_qty", "low_threshold",
                  "cost_per_unit", "supplier"]


ModifierGroupFormSet = forms.inlineformset_factory(
    MenuItem,
    ModifierGroup,
    fields=["name", "min_select", "max_select", "is_required", "display_order"],
    extra=1,
    can_delete=True,
)

ModifierOptionFormSet = forms.inlineformset_factory(
    ModifierGroup,
    ModifierOption,
    fields=["name", "price_delta", "is_available", "display_order"],
    extra=1,
    can_delete=True,
)

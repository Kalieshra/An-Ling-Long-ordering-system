"""Unit tests for menu forms — including image size cap."""
from io import BytesIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from menu.forms import MAX_UPLOAD_BYTES, CategoryForm, MenuItemForm
from menu.models import Category
from PIL import Image


def _real_image_bytes(size_bytes: int) -> bytes:
    """Return a real PNG image padded to ~size_bytes."""
    img = Image.new("RGB", (10, 10), color="red")
    buf = BytesIO()
    img.save(buf, format="PNG")
    base = buf.getvalue()
    if len(base) < size_bytes:
        base = base + b"\x00" * (size_bytes - len(base))
    return base


@pytest.mark.django_db
class TestCategoryForm:
    def test_valid_payload_saves(self):
        form = CategoryForm(data={"name": "Pizzas", "slug": "pizzas",
                                   "display_order": 0, "is_active": True})
        assert form.is_valid(), form.errors
        cat = form.save()
        assert cat.slug == "pizzas"

    def test_image_size_over_cap_rejected(self):
        big = SimpleUploadedFile(
            "big.png", _real_image_bytes(MAX_UPLOAD_BYTES + 100), content_type="image/png"
        )
        form = CategoryForm(
            data={"name": "X", "slug": "x", "display_order": 0, "is_active": True},
            files={"image": big},
        )
        assert not form.is_valid()
        assert "image" in form.errors


@pytest.mark.django_db
class TestMenuItemForm:
    def _category(self):
        return Category.objects.create(name="Pizzas", slug="pizzas")

    def test_valid_payload_saves(self):
        cat = self._category()
        form = MenuItemForm(data={
            "category": cat.pk, "name": "Margherita",
            "name_ar": "", "description": "",
            "item_type": "dish", "price": "85.00", "cost": "30.00",
            "is_available": True, "prep_time_min": 10, "tags": "[]",
        })
        assert form.is_valid(), form.errors

    def test_image_size_over_cap_rejected(self):
        cat = self._category()
        big = SimpleUploadedFile(
            "big.png", _real_image_bytes(MAX_UPLOAD_BYTES + 100), content_type="image/png"
        )
        form = MenuItemForm(
            data={
                "category": cat.pk, "name": "Margherita",
                "name_ar": "", "description": "",
                "item_type": "dish", "price": "85.00", "cost": "0",
                "is_available": True, "prep_time_min": 10, "tags": "[]",
            },
            files={"image": big},
        )
        assert not form.is_valid()
        assert "image" in form.errors

    def test_negative_price_rejected(self):
        cat = self._category()
        form = MenuItemForm(data={
            "category": cat.pk, "name": "X",
            "name_ar": "", "description": "",
            "item_type": "dish", "price": "-1.00", "cost": "0",
            "is_available": True, "prep_time_min": 10, "tags": "[]",
        })
        assert not form.is_valid()
        assert "price" in form.errors

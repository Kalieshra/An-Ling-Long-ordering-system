"""Unit test for `manage.py seed_demo`."""
import pytest
from django.core.management import call_command

pytestmark = pytest.mark.django_db


def test_seed_demo_creates_expected_objects(django_user_model):
    from menu.models import Category, MenuItem, ModifierGroup
    from orders.models import Table

    call_command("seed_demo")

    # Per spec: 3 categories, 12 dishes, 6 drinks, 5 modifier groups, 4 tables.
    assert Category.objects.count() == 3
    assert MenuItem.objects.filter(item_type="dish").count() == 12
    assert MenuItem.objects.filter(item_type="drink").count() == 6
    assert ModifierGroup.objects.count() == 5
    assert Table.objects.count() == 4

    # Users: 1 admin, 1 cashier, 1 kitchen, 2 customers.
    assert django_user_model.objects.filter(role="admin").count() == 1
    assert django_user_model.objects.filter(role="cashier").count() == 1
    assert django_user_model.objects.filter(role="kitchen").count() == 1
    assert django_user_model.objects.filter(role="customer").count() == 2


def test_seed_demo_is_idempotent(django_user_model):
    from menu.models import Category

    call_command("seed_demo")
    call_command("seed_demo")  # Should not raise; should not duplicate

    assert Category.objects.count() == 3

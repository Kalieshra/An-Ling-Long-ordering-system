"""Integration tests for /api/v1/menu/featured/ — including the 60s cache."""
from decimal import Decimal

import pytest
from django.core.cache import cache
from menu.models import Category, MenuItem
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db


@pytest.fixture
def category():
    return Category.objects.create(name="Pizzas", slug="pizzas")


@pytest.fixture
def margherita(category):
    return MenuItem.objects.create(
        category=category,
        name="Margherita",
        price=Decimal("100"),
        tags=["featured"],
    )


@pytest.fixture
def pepperoni(category):
    return MenuItem.objects.create(category=category, name="Pepperoni", price=Decimal("120"))


class TestFeatured:
    URL = "/api/v1/menu/featured/"

    def test_returns_only_items_tagged_featured(self, margherita, pepperoni):
        c = APIClient()
        resp = c.get(self.URL)
        assert resp.status_code == 200
        names = [i["name"] for i in resp.data["results"]]
        assert "Margherita" in names
        assert "Pepperoni" not in names

    def test_anonymous_access(self, margherita):
        c = APIClient()
        resp = c.get(self.URL)
        assert resp.status_code == 200

    def test_cache_hit_skips_db(self, margherita, django_assert_num_queries):
        c = APIClient()
        # First call: 1+ queries (cache miss)
        c.get(self.URL)
        # Second call: zero queries (cache hit)
        with django_assert_num_queries(0):
            resp = c.get(self.URL)
        assert resp.status_code == 200
        assert any(i["name"] == "Margherita" for i in resp.data["results"])

    def test_cache_invalidates_with_clear(self, margherita, pepperoni):
        c = APIClient()
        c.get(self.URL)
        # Mark pepperoni as featured AFTER first call
        pepperoni.tags = ["featured"]
        pepperoni.save()
        # Without cache clear, the response is stale
        resp_stale = c.get(self.URL)
        names_stale = [i["name"] for i in resp_stale.data["results"]]
        assert "Pepperoni" not in names_stale
        # After cache clear, the new featured shows up
        cache.clear()
        resp_fresh = c.get(self.URL)
        names_fresh = [i["name"] for i in resp_fresh.data["results"]]
        assert "Pepperoni" in names_fresh

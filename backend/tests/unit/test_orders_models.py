"""Unit tests for Order model — number generation, manager filters."""

import pytest
from orders.models import Order, Table

pytestmark = pytest.mark.django_db


class TestOrderNumberGeneration:
    def test_first_order_today_gets_seq_0001(self, settings):
        from django.utils import timezone
        today = timezone.localdate()
        Order.objects.all().delete()
        n = Order.next_number_for(today)
        assert n == f"{today:%Y%m%d}-0001"

    def test_second_order_today_gets_seq_0002(self):
        # Pre-populate one order today
        Order.objects.create(order_type=Order.Type.TAKEAWAY, number="prefill-0001")
        from django.utils import timezone
        today = timezone.localdate()
        n = Order.next_number_for(today)
        assert n.endswith("-0002")


class TestOrderManagerFilters:
    def test_kitchen_visible_excludes_draft_and_served(self):
        Order.objects.create(order_type=Order.Type.TAKEAWAY, status=Order.Status.DRAFT, number="d1")
        Order.objects.create(order_type=Order.Type.TAKEAWAY, status=Order.Status.CONFIRMED, number="c1")
        Order.objects.create(order_type=Order.Type.TAKEAWAY, status=Order.Status.PREPARING, number="p1")
        Order.objects.create(order_type=Order.Type.TAKEAWAY, status=Order.Status.READY, number="r1")
        Order.objects.create(order_type=Order.Type.TAKEAWAY, status=Order.Status.SERVED, number="s1")
        numbers = sorted(o.number for o in Order.objects.kitchen_visible())
        assert numbers == ["c1", "p1", "r1"]


class TestTable:
    def test_str_renders_with_number(self):
        t = Table.objects.create(number=7, capacity=4)
        assert str(t) == "Table 7"

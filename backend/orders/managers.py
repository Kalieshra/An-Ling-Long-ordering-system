"""Querysets for orders — keeps view code thin."""
from django.db import models


class OrderQuerySet(models.QuerySet):
    def kitchen_visible(self):
        from .models import Order
        return self.filter(
            status__in=[Order.Status.CONFIRMED, Order.Status.PREPARING, Order.Status.READY]
        )

    def for_customer(self, user):
        return self.filter(customer=user)

    def pending(self):
        from .models import Order
        return self.filter(status=Order.Status.PENDING)


class OrderManager(models.Manager.from_queryset(OrderQuerySet)):
    pass

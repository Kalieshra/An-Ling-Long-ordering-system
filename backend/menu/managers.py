"""Custom managers for menu queryset patterns."""
from django.db import models


class MenuItemManager(models.Manager):
    def available(self):
        """Items that are available AND in an active category."""
        return self.filter(is_available=True, category__is_active=True)

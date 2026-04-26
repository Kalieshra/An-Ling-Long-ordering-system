"""User and Role models. Session-auth for staff, JWT for customers."""
from django.contrib.auth.models import AbstractUser
from django.db import models

from .managers import UserManager


class Role(models.TextChoices):
    ADMIN = "admin", "Administrator"
    CASHIER = "cashier", "Cashier"
    KITCHEN = "kitchen", "Kitchen staff"
    CUSTOMER = "customer", "Customer"


class User(AbstractUser):
    username = None  # disable — we use email
    email = models.EmailField("email address", unique=True)
    role = models.CharField(
        max_length=16, choices=Role.choices, default=Role.CUSTOMER, db_index=True
    )
    phone = models.CharField(max_length=20, blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []

    objects = UserManager()

    class Meta:
        indexes = [models.Index(fields=["role", "is_active"])]

    def __str__(self) -> str:
        return self.email

    def is_role(self, role: "Role | str") -> bool:
        return self.role == role


class SavedAddress(models.Model):
    """A customer's saved delivery address. Set `is_default=True` to make it
    the prefilled address on the next /api/v1/orders/ POST."""

    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="saved_addresses",
    )
    label = models.CharField(max_length=40, help_text="e.g. Home, Office")
    line1 = models.CharField(max_length=200)
    line2 = models.CharField(max_length=200, blank=True)
    city = models.CharField(max_length=80)
    phone = models.CharField(max_length=20)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-is_default", "-created_at"]
        indexes = [models.Index(fields=["user", "-is_default"])]

    def __str__(self) -> str:
        return f"{self.label} — {self.line1}"

    def save(self, *args, **kwargs):
        # Demote any other default address for this user when this one is default.
        if self.is_default:
            SavedAddress.objects.filter(user=self.user, is_default=True).exclude(
                pk=self.pk
            ).update(is_default=False)
        super().save(*args, **kwargs)

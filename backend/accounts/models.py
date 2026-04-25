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

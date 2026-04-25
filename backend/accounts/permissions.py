"""DRF permission classes that check the authenticated user's role.

Usage::

    from accounts.permissions import IsAdmin, HasRole
    from accounts.models import Role

    class MenuAdminViewSet(ViewSet):
        permission_classes = [IsAdmin]            # preset

    class CrossRoleViewSet(ViewSet):
        permission_classes = [HasRole(Role.ADMIN, Role.CASHIER)]   # multiple roles
"""
from rest_framework.permissions import BasePermission

from .models import Role


class HasRole(BasePermission):
    """Allow access only to users whose role is in `allowed_roles`."""

    def __init__(self, *allowed_roles: str) -> None:
        self.allowed_roles = set(allowed_roles)

    def __call__(self):
        # DRF instantiates permission classes without args. When used as
        # `HasRole(Role.X)` we already have an instance — return self so DRF
        # uses the pre-configured one.
        return self

    def has_permission(self, request, view) -> bool:
        user = getattr(request, "user", None)
        if user is None or not user.is_authenticated:
            return False
        return user.role in self.allowed_roles


class IsAdmin(HasRole):
    def __init__(self) -> None:
        super().__init__(Role.ADMIN)


class IsCashier(HasRole):
    def __init__(self) -> None:
        super().__init__(Role.CASHIER)


class IsKitchen(HasRole):
    def __init__(self) -> None:
        super().__init__(Role.KITCHEN)


class IsCustomer(HasRole):
    def __init__(self) -> None:
        super().__init__(Role.CUSTOMER)

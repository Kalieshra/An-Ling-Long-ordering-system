"""Unit tests for HasRole permission class."""
from unittest.mock import MagicMock

from accounts.models import Role
from accounts.permissions import HasRole, IsAdmin, IsCashier, IsCustomer, IsKitchen


def _fake_request(authenticated=True, role=Role.CUSTOMER):
    req = MagicMock()
    req.user.is_authenticated = authenticated
    req.user.role = role
    return req


class TestHasRole:
    def test_denies_anonymous(self):
        perm = HasRole(Role.ADMIN)
        assert perm.has_permission(_fake_request(authenticated=False), None) is False

    def test_denies_wrong_role(self):
        perm = HasRole(Role.ADMIN)
        assert perm.has_permission(_fake_request(role=Role.CASHIER), None) is False

    def test_allows_correct_role(self):
        perm = HasRole(Role.ADMIN)
        assert perm.has_permission(_fake_request(role=Role.ADMIN), None) is True

    def test_multiple_roles_allowed(self):
        perm = HasRole(Role.ADMIN, Role.CASHIER)
        assert perm.has_permission(_fake_request(role=Role.CASHIER), None) is True
        assert perm.has_permission(_fake_request(role=Role.KITCHEN), None) is False


class TestPresetPermissions:
    def test_is_admin(self):
        assert IsAdmin().has_permission(_fake_request(role=Role.ADMIN), None)
        assert not IsAdmin().has_permission(_fake_request(role=Role.CUSTOMER), None)

    def test_is_cashier(self):
        assert IsCashier().has_permission(_fake_request(role=Role.CASHIER), None)

    def test_is_kitchen(self):
        assert IsKitchen().has_permission(_fake_request(role=Role.KITCHEN), None)

    def test_is_customer(self):
        assert IsCustomer().has_permission(_fake_request(role=Role.CUSTOMER), None)

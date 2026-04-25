"""Unit tests for the custom User model and Role enum."""
import pytest

from accounts.models import Role, User


@pytest.mark.django_db
class TestUserModel:
    def test_role_choices_contain_four_mvp_roles(self):
        values = {choice[0] for choice in Role.choices}
        assert values == {"admin", "cashier", "kitchen", "customer"}

    def test_create_user_with_email_succeeds(self):
        user = User.objects.create_user(
            email="alice@example.com", password="s3cret-pw", role=Role.CASHIER
        )
        assert user.email == "alice@example.com"
        assert user.role == "cashier"
        assert user.check_password("s3cret-pw")
        assert user.is_active
        assert not user.is_staff
        assert not user.is_superuser

    def test_create_user_requires_email(self):
        with pytest.raises(ValueError, match="email"):
            User.objects.create_user(email="", password="x", role=Role.CUSTOMER)

    def test_create_user_normalizes_email(self):
        user = User.objects.create_user(
            email="Alice@EXAMPLE.com", password="s3cret-pw", role=Role.CUSTOMER
        )
        assert user.email == "Alice@example.com"  # Django normalizes domain only

    def test_default_role_is_customer(self):
        user = User.objects.create_user(email="bob@example.com", password="s3cret-pw")
        assert user.role == Role.CUSTOMER

    def test_create_superuser_is_admin_role(self):
        admin = User.objects.create_superuser(email="admin@example.com", password="s3cret-pw")
        assert admin.role == Role.ADMIN
        assert admin.is_superuser
        assert admin.is_staff

    def test_email_is_username_field(self):
        assert User.USERNAME_FIELD == "email"
        assert "email" not in User.REQUIRED_FIELDS

    def test_email_must_be_unique(self):
        User.objects.create_user(email="dup@example.com", password="s3cret-pw")
        with pytest.raises(Exception):  # IntegrityError at DB layer
            User.objects.create_user(email="dup@example.com", password="s3cret-pw")

    def test_str_returns_email(self):
        user = User.objects.create_user(email="who@example.com", password="s3cret-pw")
        assert str(user) == "who@example.com"

    def test_is_role_helper(self):
        user = User.objects.create_user(
            email="k@example.com", password="s3cret-pw", role=Role.KITCHEN
        )
        assert user.is_role(Role.KITCHEN)
        assert not user.is_role(Role.CASHIER)

"""Unit tests for the SavedAddress model."""
import pytest
from accounts.models import SavedAddress

pytestmark = pytest.mark.django_db


@pytest.fixture
def customer(django_user_model):
    return django_user_model.objects.create_user(
        email="alice@x.com", password="alice-pw-long-enough", role="customer"
    )


class TestSavedAddress:
    def test_str_renders_label_and_first_line(self, customer):
        addr = SavedAddress.objects.create(
            user=customer,
            label="Home",
            line1="10 Cairo Street",
            city="Zagazig",
            phone="0100",
        )
        assert "Home" in str(addr)
        assert "10 Cairo Street" in str(addr)

    def test_user_can_own_multiple_addresses(self, customer):
        SavedAddress.objects.create(user=customer, label="Home", line1="A", city="Z", phone="0")
        SavedAddress.objects.create(user=customer, label="Work", line1="B", city="Z", phone="0")
        assert customer.saved_addresses.count() == 2

    def test_default_is_unique_per_user(self, customer):
        SavedAddress.objects.create(
            user=customer, label="Home", line1="A", city="Z", phone="0", is_default=True
        )
        # A second default for the SAME user should NOT raise — save() override
        # demotes the previous default.
        a2 = SavedAddress.objects.create(
            user=customer, label="Office", line1="B", city="Z", phone="0", is_default=True
        )
        a2.refresh_from_db()
        assert a2.is_default is True
        first = SavedAddress.objects.get(label="Home")
        assert first.is_default is False

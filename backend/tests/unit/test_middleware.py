"""Unit tests for AllowedRoleForPath middleware."""
from unittest.mock import MagicMock

import pytest
from accounts.middleware import AllowedRoleForPath
from accounts.models import Role, User
from django.http import HttpResponse
from django.test import RequestFactory


def _get_response(request):
    return HttpResponse("ok")


@pytest.fixture
def rf():
    return RequestFactory()


@pytest.fixture
def mw():
    return AllowedRoleForPath(_get_response)


@pytest.mark.django_db
class TestAllowedRoleForPath:
    def test_non_staff_path_passes_through_anonymous(self, rf, mw):
        request = rf.get("/api/v1/menu/items/")
        request.user = MagicMock(is_authenticated=False)
        resp = mw(request)
        assert resp.status_code == 200

    def test_anonymous_on_dashboard_redirects_to_login(self, rf, mw):
        request = rf.get("/dashboard/")
        request.user = MagicMock(is_authenticated=False)
        resp = mw(request)
        assert resp.status_code == 302
        assert "/login/" in resp["Location"]
        assert "next=%2Fdashboard%2F" in resp["Location"]

    def test_cashier_on_dashboard_gets_403(self, rf, mw):
        user = User.objects.create_user(
            email="c@example.com", password="pw-long-enough", role=Role.CASHIER
        )
        request = rf.get("/dashboard/")
        request.user = user
        resp = mw(request)
        assert resp.status_code == 403

    def test_admin_on_dashboard_passes(self, rf, mw):
        user = User.objects.create_user(
            email="a@example.com", password="pw-long-enough", role=Role.ADMIN
        )
        request = rf.get("/dashboard/")
        request.user = user
        resp = mw(request)
        assert resp.status_code == 200

    def test_customer_on_cashier_gets_403(self, rf, mw):
        user = User.objects.create_user(
            email="cust@example.com", password="pw-long-enough", role=Role.CUSTOMER
        )
        request = rf.get("/cashier/")
        request.user = user
        resp = mw(request)
        assert resp.status_code == 403

    def test_kitchen_on_kitchen_passes(self, rf, mw):
        user = User.objects.create_user(
            email="k@example.com", password="pw-long-enough", role=Role.KITCHEN
        )
        request = rf.get("/kitchen/")
        request.user = user
        resp = mw(request)
        assert resp.status_code == 200

    def test_deep_url_under_staff_prefix_also_gated(self, rf, mw):
        user = User.objects.create_user(
            email="c@example.com", password="pw-long-enough", role=Role.CASHIER
        )
        request = rf.get("/dashboard/menu/edit/42/")
        request.user = user
        resp = mw(request)
        assert resp.status_code == 403

    def test_admin_cannot_open_cashier(self, rf, mw):
        user = User.objects.create_user(
            email="a@example.com", password="pw-long-enough", role=Role.ADMIN
        )
        request = rf.get("/cashier/")
        request.user = user
        resp = mw(request)
        # Strict per spec §4.5: ADMIN does NOT auto-access /cashier/ or /kitchen/
        assert resp.status_code == 403

    def test_admin_cannot_open_kitchen(self, rf, mw):
        user = User.objects.create_user(
            email="a@example.com", password="pw-long-enough", role=Role.ADMIN
        )
        request = rf.get("/kitchen/")
        request.user = user
        resp = mw(request)
        assert resp.status_code == 403

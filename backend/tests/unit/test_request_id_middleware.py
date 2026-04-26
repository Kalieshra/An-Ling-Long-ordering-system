"""Unit tests for RequestIdMiddleware."""
import pytest
from django.test import RequestFactory
from rms.middleware import RequestIdMiddleware

pytestmark = pytest.mark.django_db


@pytest.fixture
def factory():
    return RequestFactory()


class TestRequestIdMiddleware:
    def test_generates_request_id_when_not_provided(self, factory):
        captured = {}

        def fake_response(request):
            captured["request"] = request
            from django.http import HttpResponse
            return HttpResponse("ok")

        mw = RequestIdMiddleware(fake_response)
        resp = mw(factory.get("/x/"))
        assert resp.status_code == 200
        assert "X-Request-ID" in resp
        # Generated ID looks like a UUID hex (32 chars) or similar token
        assert len(resp["X-Request-ID"]) >= 8
        # Same ID was set on the request before the view ran
        assert captured["request"].request_id == resp["X-Request-ID"]

    def test_propagates_provided_request_id(self, factory):
        provided = "client-rid-abc-123"

        def fake_response(request):
            from django.http import HttpResponse
            return HttpResponse("ok")

        mw = RequestIdMiddleware(fake_response)
        resp = mw(factory.get("/x/", HTTP_X_REQUEST_ID=provided))
        assert resp["X-Request-ID"] == provided

    def test_rejects_pathological_inbound_id(self, factory):
        # Reject overly long inbound IDs (DoS protection); generate a fresh one.
        bad = "x" * 1024

        def fake_response(request):
            from django.http import HttpResponse
            return HttpResponse("ok")

        mw = RequestIdMiddleware(fake_response)
        resp = mw(factory.get("/x/", HTTP_X_REQUEST_ID=bad))
        assert resp["X-Request-ID"] != bad
        assert len(resp["X-Request-ID"]) <= 64

"""Async tests for orders WebSocket consumers."""
import pytest
from channels.layers import get_channel_layer
from channels.testing import WebsocketCommunicator
from rms.asgi import application

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.asyncio]


@pytest.fixture
def kitchen_user(django_user_model, db):
    return django_user_model.objects.create_user(
        email="kit@x.com", password="kit-pw-long-enough", role="kitchen"
    )


@pytest.fixture
def cashier_user(django_user_model, db):
    return django_user_model.objects.create_user(
        email="cash@x.com", password="cash-pw-long-enough", role="cashier"
    )


def _app_with_user(user):
    """Wrap `application` so scope['user'] is preset to `user` for every WS.
    Bypasses session/JWT middleware for unit-style consumer tests."""
    inner = application

    async def asgi(scope, receive, send):
        scope["user"] = user
        return await inner(scope, receive, send)

    return asgi


class TestKDSConsumerAuth:
    async def test_anonymous_connection_rejected(self):
        from django.contrib.auth.models import AnonymousUser
        comm = WebsocketCommunicator(_app_with_user(AnonymousUser()), "/ws/kds/")
        connected, close_code = await comm.connect()
        assert connected is False
        assert close_code == 4401

    async def test_cashier_connection_rejected(self, cashier_user):
        comm = WebsocketCommunicator(_app_with_user(cashier_user), "/ws/kds/")
        connected, close_code = await comm.connect()
        assert connected is False
        assert close_code == 4401

    async def test_kitchen_connection_accepted(self, kitchen_user):
        comm = WebsocketCommunicator(_app_with_user(kitchen_user), "/ws/kds/")
        connected, _ = await comm.connect()
        assert connected is True
        await comm.disconnect()


class TestKDSConsumerBroadcast:
    async def test_kitchen_receives_order_new_from_channel_layer(self, kitchen_user):
        comm = WebsocketCommunicator(_app_with_user(kitchen_user), "/ws/kds/")
        connected, _ = await comm.connect()
        assert connected is True

        layer = get_channel_layer()
        await layer.group_send(
            "kds",
            {
                "type": "order.new",
                "payload": {"uuid": "u-1", "number": "20260426-0001", "status": "confirmed"},
            },
        )

        msg = await comm.receive_json_from(timeout=2)
        assert msg["event"] == "order.new"
        assert msg["payload"]["number"] == "20260426-0001"
        await comm.disconnect()

    async def test_kitchen_receives_order_updated(self, kitchen_user):
        comm = WebsocketCommunicator(_app_with_user(kitchen_user), "/ws/kds/")
        await comm.connect()

        layer = get_channel_layer()
        await layer.group_send(
            "kds",
            {"type": "order.updated", "payload": {"uuid": "u-1", "status": "preparing"}},
        )

        msg = await comm.receive_json_from(timeout=2)
        assert msg["event"] == "order.updated"
        assert msg["payload"]["status"] == "preparing"
        await comm.disconnect()

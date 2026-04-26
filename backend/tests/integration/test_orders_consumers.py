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
        connected, _ = await comm.connect()
        # Accept before close means we got accept, now check for the close
        assert connected is True
        # Receive the close frame
        disconnect_code = await comm.receive_output(timeout=1)
        assert disconnect_code["type"] == "websocket.close"
        assert disconnect_code.get("code") == 4401

    async def test_cashier_connection_rejected(self, cashier_user):
        comm = WebsocketCommunicator(_app_with_user(cashier_user), "/ws/kds/")
        connected, _ = await comm.connect()
        # Accept before close means we got accept, now check for the close
        assert connected is True
        # Receive the close frame
        disconnect_code = await comm.receive_output(timeout=1)
        assert disconnect_code["type"] == "websocket.close"
        assert disconnect_code.get("code") == 4401

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


@pytest.fixture
def customer_user(django_user_model, db):
    return django_user_model.objects.create_user(
        email="alice@x.com", password="alice-pw-long-enough", role="customer"
    )


@pytest.fixture
def order(customer_user, db):
    from decimal import Decimal

    from menu.models import Category, MenuItem
    from orders.models import Order
    from orders.services import create_order

    cat = Category.objects.create(name="P", slug="p")
    mi = MenuItem.objects.create(category=cat, name="MI", price=Decimal("10"))
    return create_order(
        cart=[{"menu_item": mi.id, "quantity": 1, "modifiers": []}],
        customer=customer_user,
        order_type=Order.Type.TAKEAWAY,
        initial_status=Order.Status.PENDING,
    )


class TestOrderTrackConsumerAuth:
    async def test_anonymous_rejected(self, order):
        from django.contrib.auth.models import AnonymousUser
        comm = WebsocketCommunicator(
            _app_with_user(AnonymousUser()),
            f"/ws/order/{order.uuid}/",
        )
        connected, _ = await comm.connect()
        # Accept before close means we got accept, now check for the close
        assert connected is True
        # Receive the close frame
        disconnect_code = await comm.receive_output(timeout=1)
        assert disconnect_code["type"] == "websocket.close"
        assert disconnect_code.get("code") == 4401

    async def test_other_customer_rejected(self, order, django_user_model):
        from asgiref.sync import sync_to_async
        other = await sync_to_async(django_user_model.objects.create_user)(
            email="other@x.com", password="other-pw-long-enough", role="customer"
        )
        comm = WebsocketCommunicator(
            _app_with_user(other),
            f"/ws/order/{order.uuid}/",
        )
        connected, _ = await comm.connect()
        # Accept before close means we got accept, now check for the close
        assert connected is True
        # Receive the close frame
        disconnect_code = await comm.receive_output(timeout=1)
        assert disconnect_code["type"] == "websocket.close"
        assert disconnect_code.get("code") == 4403

    async def test_owner_accepted(self, order, customer_user):
        comm = WebsocketCommunicator(
            _app_with_user(customer_user),
            f"/ws/order/{order.uuid}/",
        )
        connected, _ = await comm.connect()
        assert connected is True
        await comm.disconnect()


class TestOrderTrackConsumerBroadcast:
    async def test_owner_receives_order_updated(self, order, customer_user):
        comm = WebsocketCommunicator(
            _app_with_user(customer_user),
            f"/ws/order/{order.uuid}/",
        )
        await comm.connect()

        layer = get_channel_layer()
        await layer.group_send(
            f"order_{order.uuid}",
            {
                "type": "order.updated",
                "payload": {"uuid": str(order.uuid), "status": "preparing"},
            },
        )
        msg = await comm.receive_json_from(timeout=2)
        assert msg["event"] == "order.updated"
        assert msg["payload"]["status"] == "preparing"
        await comm.disconnect()


class TestKDSReconnect:
    async def test_reconnect_within_5s_still_receives_broadcasts(self, kitchen_user):
        # First connection
        comm1 = WebsocketCommunicator(_app_with_user(kitchen_user), "/ws/kds/")
        connected, _ = await comm1.connect()
        assert connected
        await comm1.disconnect()

        # Second connection (simulates browser reconnect)
        comm2 = WebsocketCommunicator(_app_with_user(kitchen_user), "/ws/kds/")
        connected2, _ = await comm2.connect()
        assert connected2

        layer = get_channel_layer()
        await layer.group_send(
            "kds",
            {"type": "order.new", "payload": {"uuid": "x", "number": "X-1", "status": "confirmed"}},
        )
        msg = await comm2.receive_json_from(timeout=2)
        assert msg["payload"]["number"] == "X-1"
        await comm2.disconnect()

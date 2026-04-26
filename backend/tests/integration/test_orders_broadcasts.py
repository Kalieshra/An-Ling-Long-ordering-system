"""Verify state-changing services emit channel-layer broadcasts to the right groups."""
from decimal import Decimal

import pytest
from asgiref.sync import sync_to_async
from channels.testing import WebsocketCommunicator
from rms.asgi import application

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.asyncio]


@pytest.fixture
def kitchen_user(django_user_model, db):
    return django_user_model.objects.create_user(
        email="kit@x.com", password="kit-pw-long-enough", role="kitchen"
    )


@pytest.fixture
def customer_user(django_user_model, db):
    return django_user_model.objects.create_user(
        email="alice@x.com", password="alice-pw-long-enough", role="customer"
    )


@pytest.fixture
def margherita(db):
    from menu.models import Category, MenuItem
    cat = Category.objects.create(name="P", slug="p")
    return MenuItem.objects.create(category=cat, name="Marg", price=Decimal("10"))


def _app_with_user(user):
    inner = application

    async def asgi(scope, receive, send):
        scope["user"] = user
        return await inner(scope, receive, send)

    return asgi


async def _acall(fn, *args, **kwargs):
    return await sync_to_async(fn)(*args, **kwargs)


class TestConfirmOrderBroadcasts:
    async def test_confirm_order_broadcasts_order_new_to_kds(self, margherita, customer_user, kitchen_user):
        from orders.models import Order
        from orders.services import confirm_order, create_order

        # Subscribe a kitchen WS first
        kds = WebsocketCommunicator(_app_with_user(kitchen_user), "/ws/kds/")
        connected, _ = await kds.connect()
        assert connected

        # Create + confirm an order — should fan out
        order = await _acall(
            create_order,
            cart=[{"menu_item": margherita.id, "quantity": 1, "modifiers": []}],
            customer=customer_user,
            order_type=Order.Type.TAKEAWAY,
            initial_status=Order.Status.PENDING,
        )
        await _acall(confirm_order, order)

        msg = await kds.receive_json_from(timeout=2)
        assert msg["event"] == "order.new"
        assert msg["payload"]["uuid"] == str(order.uuid)
        assert msg["payload"]["status"] == "confirmed"
        await kds.disconnect()


class TestUpdateOrderStatusBroadcasts:
    async def test_update_status_broadcasts_to_both_groups(self, margherita, customer_user, kitchen_user):
        from orders.models import Order
        from orders.services import confirm_order, create_order, update_order_status

        order = await _acall(
            create_order,
            cart=[{"menu_item": margherita.id, "quantity": 1, "modifiers": []}],
            customer=customer_user,
            order_type=Order.Type.TAKEAWAY,
            initial_status=Order.Status.PENDING,
        )
        await _acall(confirm_order, order)

        kds = WebsocketCommunicator(_app_with_user(kitchen_user), "/ws/kds/")
        await kds.connect()
        track = WebsocketCommunicator(
            _app_with_user(customer_user), f"/ws/order/{order.uuid}/"
        )
        await track.connect()

        await _acall(
            update_order_status, order, Order.Status.PREPARING, by_user=kitchen_user,
        )

        kds_msg = await kds.receive_json_from(timeout=2)
        track_msg = await track.receive_json_from(timeout=2)
        assert kds_msg["event"] == "order.updated"
        assert kds_msg["payload"]["status"] == "preparing"
        assert track_msg["event"] == "order.updated"
        assert track_msg["payload"]["status"] == "preparing"

        await kds.disconnect()
        await track.disconnect()


class TestCashierConfirmBroadcasts:
    async def test_cashier_confirm_pending_broadcasts(self, margherita, customer_user, kitchen_user):
        from orders.models import Order
        from orders.services import confirm_order, create_order

        # customer-API style pending order
        order = await _acall(
            create_order,
            cart=[{"menu_item": margherita.id, "quantity": 1, "modifiers": []}],
            customer=customer_user,
            order_type=Order.Type.TAKEAWAY,
            initial_status=Order.Status.PENDING,
        )

        kds = WebsocketCommunicator(_app_with_user(kitchen_user), "/ws/kds/")
        await kds.connect()

        # Cashier clicks "confirm" on the pending panel — calls confirm_order
        await _acall(confirm_order, order)

        msg = await kds.receive_json_from(timeout=2)
        assert msg["event"] == "order.new"
        assert msg["payload"]["uuid"] == str(order.uuid)
        await kds.disconnect()


class TestCancelBroadcasts:
    async def test_cancel_order_broadcasts_to_kds_and_customer(self, margherita, customer_user, kitchen_user):
        from orders.models import Order
        from orders.services import cancel_order, create_order

        order = await _acall(
            create_order,
            cart=[{"menu_item": margherita.id, "quantity": 1, "modifiers": []}],
            customer=customer_user,
            order_type=Order.Type.TAKEAWAY,
            initial_status=Order.Status.PENDING,
        )

        kds = WebsocketCommunicator(_app_with_user(kitchen_user), "/ws/kds/")
        await kds.connect()
        track = WebsocketCommunicator(_app_with_user(customer_user), f"/ws/order/{order.uuid}/")
        await track.connect()

        await _acall(cancel_order, order)

        kds_msg = await kds.receive_json_from(timeout=2)
        track_msg = await track.receive_json_from(timeout=2)
        assert kds_msg["payload"]["status"] == "cancelled"
        assert track_msg["payload"]["status"] == "cancelled"

        await kds.disconnect()
        await track.disconnect()

"""WebSocket consumers for the kitchen display (KDS) and customer order tracking.

Both consumers are async + JSON. They never query the DB themselves — every
inbound state mutation comes through `orders.services` (HTTP path). The
consumers are only responsible for:
  - authorising the connection (role check)
  - joining/leaving the right channel group
  - relaying group broadcasts to the WebSocket as JSON
"""
from accounts.models import Role
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer


class KDSConsumer(AsyncJsonWebsocketConsumer):
    """Kitchen Display System consumer. All kitchen staff join the `kds` group."""

    GROUP = "kds"

    async def connect(self):
        user = self.scope.get("user")
        if user is None or not user.is_authenticated or user.role != Role.KITCHEN:
            # Accept first so the browser receives a proper close frame with the
            # custom code (4401).  Closing before accept() produces an abnormal
            # close (1006) which the client cannot distinguish from a network error.
            await self.accept()
            await self.close(code=4401)
            return
        await self.channel_layer.group_add(self.GROUP, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        await self.channel_layer.group_discard(self.GROUP, self.channel_name)

    # Group-message handlers. Channels routes `{"type": "order.new"}` to
    # `order_new(self, message)` (dot becomes underscore).
    async def order_new(self, message):
        await self.send_json({"event": "order.new", "payload": message["payload"]})

    async def order_updated(self, message):
        await self.send_json({"event": "order.updated", "payload": message["payload"]})


class OrderTrackConsumer(AsyncJsonWebsocketConsumer):
    """Per-order tracking consumer for customers.

    Group name is `order_<uuid>`. Only the order's customer (matched by user id)
    may connect.
    """

    async def connect(self):
        user = self.scope.get("user")
        if user is None or not user.is_authenticated:
            await self.accept()
            await self.close(code=4401)
            return

        uuid = self.scope["url_route"]["kwargs"]["uuid"]
        order_customer_id = await self._get_order_customer_id(uuid)
        if order_customer_id is None:
            await self.accept()
            await self.close(code=4404)
            return
        if order_customer_id != user.id:
            await self.accept()
            await self.close(code=4403)
            return

        self.group_name = f"order_{uuid}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def order_updated(self, message):
        await self.send_json({"event": "order.updated", "payload": message["payload"]})

    @database_sync_to_async
    def _get_order_customer_id(self, uuid):
        from .models import Order
        try:
            return Order.objects.values_list("customer_id", flat=True).get(uuid=uuid)
        except Order.DoesNotExist:
            return None

"""WebSocket consumers for the kitchen display (KDS) and customer order tracking.

Both consumers are async + JSON. They never query the DB themselves — every
inbound state mutation comes through `orders.services` (HTTP path). The
consumers are only responsible for:
  - authorising the connection (role check)
  - joining/leaving the right channel group
  - relaying group broadcasts to the WebSocket as JSON
"""
from accounts.models import Role
from channels.generic.websocket import AsyncJsonWebsocketConsumer


class KDSConsumer(AsyncJsonWebsocketConsumer):
    """Kitchen Display System consumer. All kitchen staff join the `kds` group."""

    GROUP = "kds"

    async def connect(self):
        user = self.scope.get("user")
        if user is None or not user.is_authenticated or user.role != Role.KITCHEN:
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

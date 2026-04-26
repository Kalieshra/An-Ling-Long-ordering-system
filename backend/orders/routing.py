"""WebSocket URL patterns."""
from channels.auth import AuthMiddlewareStack
from django.urls import path

from .consumers import KDSConsumer, OrderTrackConsumer
from .middleware import JwtAuthMiddleware

websocket_urlpatterns = [
    # /ws/kds/ — kitchen staff KDS, session-auth
    path("ws/kds/", AuthMiddlewareStack(KDSConsumer.as_asgi())),
    # /ws/order/<uuid>/?token=<jwt> — customer order tracking, JWT in query string
    path("ws/order/<uuid:uuid>/", JwtAuthMiddleware(OrderTrackConsumer.as_asgi())),
]

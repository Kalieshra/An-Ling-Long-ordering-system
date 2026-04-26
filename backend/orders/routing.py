"""WebSocket URL patterns."""
from channels.auth import AuthMiddlewareStack
from django.urls import path

from .consumers import KDSConsumer

websocket_urlpatterns = [
    # /ws/kds/ — kitchen staff KDS, session-auth via AuthMiddlewareStack
    path("ws/kds/", AuthMiddlewareStack(KDSConsumer.as_asgi())),
]

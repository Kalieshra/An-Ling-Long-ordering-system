"""ASGI entry point. Routes HTTP through the standard Django ASGI app and
WebSocket through the channels URLRouter. Phase 4 onward."""
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "rms.settings.dev")

# Standard Django ASGI app must be initialised BEFORE we import anything that
# touches Django models (e.g. our consumers) — otherwise we'd hit
# AppRegistryNotReady.
from django.core.asgi import get_asgi_application  # noqa: E402

django_asgi_app = get_asgi_application()

from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402
from channels.security.websocket import AllowedHostsOriginValidator  # noqa: E402
from orders.routing import websocket_urlpatterns  # noqa: E402

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": AllowedHostsOriginValidator(URLRouter(websocket_urlpatterns)),
})

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "rms.settings.dev")
django_asgi_app = get_asgi_application()

# Phase 4 will add ProtocolTypeRouter with WebSocket routing here.
application = django_asgi_app

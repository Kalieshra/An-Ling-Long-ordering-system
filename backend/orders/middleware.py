"""ASGI middleware that authenticates a WebSocket connection via a JWT
passed in the query string: `ws://host/ws/order/<uuid>/?token=<access>`.

We can't use the standard Authorization header during the WebSocket handshake
because browser WebSocket APIs do not let us set custom headers. Query-string
JWTs are the documented best practice from `channels` + `simplejwt`.
"""
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth.models import AnonymousUser


@database_sync_to_async
def _user_from_token(raw_token: str):
    """Resolve a JWT access token to a User instance, or AnonymousUser."""
    try:
        from rest_framework_simplejwt.authentication import JWTAuthentication
        from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
    except ImportError:
        return AnonymousUser()

    auth = JWTAuthentication()
    try:
        validated = auth.get_validated_token(raw_token)
        return auth.get_user(validated)
    except (InvalidToken, TokenError, Exception):  # noqa: BLE001
        return AnonymousUser()


class JwtAuthMiddleware(BaseMiddleware):
    """Reads the `token` query parameter and assigns scope['user'] from it."""

    async def __call__(self, scope, receive, send):
        query = parse_qs(scope.get("query_string", b"").decode("utf-8"))
        token_list = query.get("token", [])
        if token_list:
            scope["user"] = await _user_from_token(token_list[0])
        elif "user" not in scope:
            scope["user"] = AnonymousUser()
        return await super().__call__(scope, receive, send)

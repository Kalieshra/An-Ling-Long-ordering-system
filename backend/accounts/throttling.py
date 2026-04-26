"""Throttle classes for sensitive auth endpoints."""
from rest_framework.throttling import AnonRateThrottle


class LoginThrottle(AnonRateThrottle):
    """Login is anonymous-by-definition; rate-limit by IP. Matches the
    `auth_login` rate from REST_FRAMEWORK.DEFAULT_THROTTLE_RATES."""

    scope = "auth_login"

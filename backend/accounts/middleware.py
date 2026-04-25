"""Role-gating middleware for staff web dashboards.

Reads STAFF_PATH_ROLES from settings (declared in rms/settings/base.py)::

    STAFF_PATH_ROLES = {
        "/dashboard/": "admin",
        "/cashier/":   "cashier",
        "/kitchen/":   "kitchen",
    }

Behavior:
- Path NOT under any staff prefix    → pass through
- Path is staff, user is anonymous   → 302 to /login/?next=<original_path>
- Path is staff, role doesn't match  → 403 (rendered via templates/403.html if available)
- Path is staff, role matches        → pass through
"""
from urllib.parse import quote

from django.conf import settings
from django.http import HttpResponseForbidden, HttpResponseRedirect
from django.template import TemplateDoesNotExist
from django.template.loader import render_to_string


class AllowedRoleForPath:
    def __init__(self, get_response):
        self.get_response = get_response
        # Order rules so the longest prefix matches first (cheap support for
        # nested prefixes if we add any in the future).
        self._rules = sorted(
            settings.STAFF_PATH_ROLES.items(), key=lambda kv: len(kv[0]), reverse=True
        )

    def __call__(self, request):
        required = self._required_role(request.path)
        if required is None:
            return self.get_response(request)

        user = getattr(request, "user", None)
        if user is None or not user.is_authenticated:
            next_url = quote(request.get_full_path(), safe="")
            return HttpResponseRedirect(f"{settings.LOGIN_URL}?next={next_url}")

        if user.role != required:
            return self._forbidden(request, required)

        return self.get_response(request)

    def _required_role(self, path: str) -> str | None:
        for prefix, role in self._rules:
            if path.startswith(prefix):
                return role
        return None

    def _forbidden(self, request, required: str):
        context = {
            "required_role": required,
            "user_role": getattr(request.user, "role", None),
        }
        try:
            body = render_to_string("403.html", context, request=request)
        except TemplateDoesNotExist:
            body = f"Forbidden. This area requires role '{required}'."
        return HttpResponseForbidden(body)

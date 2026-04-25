"""Placeholder. Task 8 will implement AllowedRoleForPath."""


class AllowedRoleForPath:
    """Pass-through stub. Real implementation lands in Task 8."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

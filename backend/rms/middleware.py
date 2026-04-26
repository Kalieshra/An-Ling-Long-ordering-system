"""Project-level middleware (request-id stamping)."""
import uuid

REQUEST_ID_HEADER = "HTTP_X_REQUEST_ID"
RESPONSE_HEADER = "X-Request-ID"
MAX_INBOUND_LEN = 64


def _is_safe_inbound(value: str) -> bool:
    """Reject overly-long or non-printable inbound IDs."""
    return 0 < len(value) <= MAX_INBOUND_LEN and value.isprintable()


class RequestIdMiddleware:
    """Generates a request ID per request and surfaces it on the response.

    - If the client provides `X-Request-ID` (and it's reasonable), reuse it.
    - Otherwise generate a UUID4 hex (32 chars).
    - The ID is stored on `request.request_id` so views and structlog can read it.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        inbound = request.META.get(REQUEST_ID_HEADER, "")
        if inbound and _is_safe_inbound(inbound):
            rid = inbound
        else:
            rid = uuid.uuid4().hex
        request.request_id = rid
        response = self.get_response(request)
        response[RESPONSE_HEADER] = rid
        return response

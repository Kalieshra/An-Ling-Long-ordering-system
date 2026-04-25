"""Domain exceptions for the orders services layer."""


class OrderValidationError(Exception):
    """Raised when input data fails validation (e.g. empty cart, unavailable item)."""


class InvalidTransition(Exception):
    """Raised when a status transition is not allowed from the current status."""

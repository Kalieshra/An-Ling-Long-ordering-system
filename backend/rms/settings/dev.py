"""Dev-only settings. Imports everything from base."""
from .base import *  # noqa: F401, F403

DEBUG = True
ALLOWED_HOSTS = ["*"]  # dev only

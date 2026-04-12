"""Shared rate limiter instance — imported by routes to avoid circular imports."""
import os

from slowapi import Limiter
from slowapi.util import get_remote_address

# Disable in test runs (TESTING=1) so rate limits don't interfere with the
# test suite, which makes many rapid requests from the same "IP".
_enabled = os.getenv("TESTING", "") not in ("1", "true", "yes")

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200/minute"],
    enabled=_enabled,
)

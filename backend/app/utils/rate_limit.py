"""Shared slowapi limiter instance — Redis-backed."""

from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import settings

# slowapi uses a string storage URI; falling back to in-memory keeps tests safe.
_storage_uri = settings.REDIS_URL if not settings.is_test else "memory://"

limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=_storage_uri,
    default_limits=["100/minute"],
    headers_enabled=False,
    enabled=not settings.is_test,
)

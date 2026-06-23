"""Async Redis connection pool with helpers and a cache decorator."""

from __future__ import annotations

import functools
import hashlib
import json
from collections.abc import Awaitable, Callable
from typing import Any, ParamSpec, TypeVar, cast

import redis.asyncio as redis
import structlog

from app.config import settings

log = structlog.get_logger(__name__)

_pool: redis.Redis | None = None

P = ParamSpec("P")
T = TypeVar("T")


async def get_redis() -> redis.Redis:
    global _pool
    if _pool is None:
        _pool = redis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            max_connections=20,
        )
    return _pool


async def close_redis() -> None:
    global _pool
    if _pool is not None:
        await _pool.aclose()
        _pool = None


async def cache_get(key: str) -> Any | None:
    client = await get_redis()
    raw = await client.get(key)
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


async def cache_set(key: str, value: Any, ttl_seconds: int) -> None:
    client = await get_redis()
    await client.set(key, json.dumps(value, default=str), ex=ttl_seconds)


async def cache_delete(*keys: str) -> None:
    if not keys:
        return
    client = await get_redis()
    await client.delete(*keys)


def _stable_key(prefix: str, args: tuple[Any, ...], kwargs: dict[str, Any]) -> str:
    payload = json.dumps(
        {"a": [str(a) for a in args], "k": {k: str(v) for k, v in sorted(kwargs.items())}},
        sort_keys=True,
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]
    return f"{prefix}:{digest}"


def cache_async(
    *, key_prefix: str, ttl_seconds: int
) -> Callable[[Callable[P, Awaitable[T]]], Callable[P, Awaitable[T]]]:
    """Wrap an async function so its return value is JSON-cached in Redis."""

    def decorator(fn: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]:
        @functools.wraps(fn)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            key = _stable_key(key_prefix, args, kwargs)
            cached = await cache_get(key)
            if cached is not None:
                return cast(T, cached)
            result = await fn(*args, **kwargs)
            try:
                await cache_set(key, result, ttl_seconds)
            except Exception:
                log.warning("redis.cache_set_failed", key_prefix=key_prefix)
            return result

        return wrapper

    return decorator

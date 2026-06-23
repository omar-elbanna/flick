"""Async TMDB v3 client with retry and Redis-backed caching."""

from __future__ import annotations

from typing import Any

import httpx
import structlog
from fastapi import HTTPException, status
from tenacity import (
    AsyncRetrying,
    RetryError,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.config import settings
from app.utils.redis_client import cache_async

log = structlog.get_logger(__name__)

TMDB_BASE_URL = "https://api.themoviedb.org/3"
TMDB_TIMEOUT = httpx.Timeout(10.0, connect=5.0)


class TMDBError(HTTPException):
    def __init__(self, message: str = "TMDB request failed.") -> None:
        super().__init__(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"detail": message, "code": "TMDB_ERROR"},
        )


async def _request(path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    full_params: dict[str, Any] = {"api_key": settings.TMDB_API_KEY}
    if params:
        full_params.update({k: v for k, v in params.items() if v is not None})

    try:
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
            retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.RequestError)),
            reraise=True,
        ):
            with attempt:
                async with httpx.AsyncClient(
                    base_url=TMDB_BASE_URL, timeout=TMDB_TIMEOUT
                ) as client:
                    resp = await client.get(path, params=full_params)
                if resp.status_code in (429, 500, 502, 503, 504):
                    resp.raise_for_status()
                if resp.status_code == 404:
                    log.info("tmdb.not_found", path=path)
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail={
                            "detail": "Movie not found.",
                            "code": "MOVIE_NOT_FOUND",
                        },
                    )
                if resp.status_code == 401:
                    log.error("tmdb.unauthorized")
                    raise TMDBError("TMDB API key is invalid.")
                if resp.status_code >= 400:
                    log.warning(
                        "tmdb.client_error",
                        status_code=resp.status_code,
                        path=path,
                    )
                    raise TMDBError(f"TMDB request failed ({resp.status_code}).")
                return resp.json()
    except RetryError as exc:
        log.error("tmdb.retry_exhausted", path=path)
        raise TMDBError("TMDB upstream unavailable.") from exc
    except httpx.HTTPError as exc:
        log.error("tmdb.request_error", path=path, error_type=type(exc).__name__)
        raise TMDBError("TMDB request failed.") from exc
    raise TMDBError("Unknown TMDB error.")


@cache_async(key_prefix="tmdb:search", ttl_seconds=3600)
async def search_movies(query: str, page: int = 1) -> dict[str, Any]:
    return await _request(
        "/search/movie",
        {"query": query, "page": page, "include_adult": "false"},
    )


@cache_async(key_prefix="tmdb:detail", ttl_seconds=86400)
async def get_movie_detail(tmdb_id: int) -> dict[str, Any]:
    return await _request(f"/movie/{tmdb_id}")


@cache_async(key_prefix="tmdb:trending", ttl_seconds=3600)
async def get_trending(page: int = 1) -> dict[str, Any]:
    return await _request("/trending/movie/week", {"page": page})


@cache_async(key_prefix="tmdb:genres", ttl_seconds=604800)
async def get_genres() -> dict[str, Any]:
    return await _request("/genre/movie/list")


@cache_async(key_prefix="tmdb:similar", ttl_seconds=21600)
async def get_similar(tmdb_id: int, page: int = 1) -> dict[str, Any]:
    return await _request(f"/movie/{tmdb_id}/similar", {"page": page})


@cache_async(key_prefix="tmdb:recs", ttl_seconds=21600)
async def get_tmdb_recommendations(tmdb_id: int, page: int = 1) -> dict[str, Any]:
    """TMDB /recommendations — curated from user behavior, much better than /similar."""

    return await _request(f"/movie/{tmdb_id}/recommendations", {"page": page})


@cache_async(key_prefix="tmdb:providers", ttl_seconds=86400)
async def get_watch_providers(tmdb_id: int) -> dict[str, Any]:
    """Where to watch a movie — streaming, rent, buy availability by country."""

    return await _request(f"/movie/{tmdb_id}/watch/providers")

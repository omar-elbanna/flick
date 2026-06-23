"""Movie endpoints — TMDB-backed search, trending, detail, genres."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import _get_session, get_current_user
from app.models.user import User
from app.schemas.movie import GenresResponse, MovieDetail, MovieSearchResponse
from app.services.movie_service import fetch_and_cache_movie
from app.utils.rate_limit import limiter
from app.utils.tmdb_client import (
    get_genres,
    get_trending,
    get_watch_providers,
    search_movies,
)

router = APIRouter()


@router.get("/search", response_model=MovieSearchResponse)
@limiter.limit("60/minute")
async def search(
    request: Request,
    q: Annotated[str, Query(min_length=1, max_length=120)],
    page: Annotated[int, Query(ge=1, le=500)] = 1,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    return await search_movies(q, page)


@router.get("/trending", response_model=MovieSearchResponse)
@limiter.limit("60/minute")
async def trending(
    request: Request,
    page: Annotated[int, Query(ge=1, le=10)] = 1,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    return await get_trending(page)


@router.get("/genres", response_model=GenresResponse)
@limiter.limit("60/minute")
async def genres(
    request: Request,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    return await get_genres()


@router.get("/{tmdb_id}", response_model=MovieDetail)
@limiter.limit("60/minute")
async def detail(
    request: Request,
    tmdb_id: int,
    db: Annotated[AsyncSession, Depends(_get_session)],
    _user: User = Depends(get_current_user),
) -> MovieDetail:
    movie = await fetch_and_cache_movie(tmdb_id, db)
    return MovieDetail.model_validate(movie)


@router.get("/{tmdb_id}/providers")
@limiter.limit("60/minute")
async def providers(
    request: Request,
    tmdb_id: int,
    country: Annotated[str, Query(min_length=2, max_length=2, pattern="^[A-Z]{2}$")] = "US",
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Streaming/rent/buy availability for a movie. Filtered to one country.

    Returns a slim payload: {flatrate:[], rent:[], buy:[], link:str|null}.
    Provider entries are {provider_id:int, provider_name:str, logo_path:str|null}.
    """

    raw = await get_watch_providers(tmdb_id)
    country_data = (raw.get("results") or {}).get(country) or {}
    return {
        "country": country,
        "link": country_data.get("link"),
        "flatrate": country_data.get("flatrate") or [],
        "rent": country_data.get("rent") or [],
        "buy": country_data.get("buy") or [],
    }

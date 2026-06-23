"""Watchlist CRUD endpoints."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import _get_session, get_current_user
from app.models.movie import Movie
from app.models.user import User
from app.models.watchlist import WatchlistItem
from app.schemas.watchlist import (
    AddWatchlistRequest,
    PaginatedWatchlist,
    UpdateWatchlistRequest,
    WatchlistItemResponse,
)
from app.services.movie_service import fetch_and_cache_movie
from app.utils.rate_limit import limiter

router = APIRouter()


def _to_response(item: WatchlistItem, movie: Movie) -> WatchlistItemResponse:
    return WatchlistItemResponse(
        id=item.id,
        movie_id=item.movie_id,
        tmdb_id=movie.tmdb_id,
        movie_title=movie.title,
        poster_path=movie.poster_path,
        added_at=item.added_at,
        watched=item.watched,
        watched_at=item.watched_at,
    )


@router.post(
    "/watchlist",
    response_model=WatchlistItemResponse,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("60/minute")
async def add_to_watchlist(
    request: Request,
    payload: AddWatchlistRequest,
    db: Annotated[AsyncSession, Depends(_get_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> WatchlistItemResponse:
    movie = await fetch_and_cache_movie(payload.tmdb_id, db)
    existing = (
        await db.execute(
            select(WatchlistItem).where(
                WatchlistItem.user_id == current_user.id,
                WatchlistItem.movie_id == movie.id,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return _to_response(existing, movie)
    item = WatchlistItem(user_id=current_user.id, movie_id=movie.id)
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return _to_response(item, movie)


@router.delete("/watchlist/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("60/minute")
async def delete_watchlist_item(
    request: Request,
    item_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(_get_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> None:
    item = await db.get(WatchlistItem, item_id)
    if item is None or item.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": "Watchlist item not found.", "code": "WATCHLIST_NOT_FOUND"},
        )
    await db.delete(item)
    await db.commit()


@router.patch("/watchlist/{item_id}", response_model=WatchlistItemResponse)
@limiter.limit("60/minute")
async def update_watchlist_item(
    request: Request,
    item_id: uuid.UUID,
    payload: UpdateWatchlistRequest,
    db: Annotated[AsyncSession, Depends(_get_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> WatchlistItemResponse:
    item = await db.get(WatchlistItem, item_id)
    if item is None or item.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": "Watchlist item not found.", "code": "WATCHLIST_NOT_FOUND"},
        )
    item.watched = payload.watched
    item.watched_at = datetime.now(tz=UTC) if payload.watched else None
    await db.commit()
    movie = await db.get(Movie, item.movie_id)
    assert movie is not None
    return _to_response(item, movie)


@router.get("/users/me/watchlist", response_model=PaginatedWatchlist)
@limiter.limit("60/minute")
async def list_my_watchlist(
    request: Request,
    db: Annotated[AsyncSession, Depends(_get_session)],
    current_user: Annotated[User, Depends(get_current_user)],
    page: Annotated[int, Query(ge=1, le=1000)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    filter: Annotated[Literal["all", "watched", "unwatched"], Query()] = "all",
) -> PaginatedWatchlist:
    base = select(WatchlistItem, Movie).join(Movie, Movie.id == WatchlistItem.movie_id).where(
        WatchlistItem.user_id == current_user.id
    )
    count_stmt = select(func.count(WatchlistItem.id)).where(
        WatchlistItem.user_id == current_user.id
    )
    if filter == "watched":
        base = base.where(WatchlistItem.watched.is_(True))
        count_stmt = count_stmt.where(WatchlistItem.watched.is_(True))
    elif filter == "unwatched":
        base = base.where(WatchlistItem.watched.is_(False))
        count_stmt = count_stmt.where(WatchlistItem.watched.is_(False))

    total = (await db.execute(count_stmt)).scalar_one()
    rows = (
        await db.execute(
            base.order_by(desc(WatchlistItem.added_at))
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()
    items = [_to_response(item, movie) for item, movie in rows]
    return PaginatedWatchlist(items=items, page=page, page_size=page_size, total=total)

"""Watchlist schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AddWatchlistRequest(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    tmdb_id: int = Field(..., ge=1)


class UpdateWatchlistRequest(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    watched: bool


class WatchlistItemResponse(BaseModel):
    model_config = ConfigDict(strict=True, from_attributes=True)

    id: uuid.UUID
    movie_id: uuid.UUID
    tmdb_id: int
    movie_title: str
    poster_path: str | None = None
    added_at: datetime
    watched: bool
    watched_at: datetime | None = None


class PaginatedWatchlist(BaseModel):
    model_config = ConfigDict(strict=True)

    items: list[WatchlistItemResponse]
    page: int
    page_size: int
    total: int

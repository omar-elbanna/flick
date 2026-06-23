"""Movie schemas."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class MovieGenre(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: int
    name: str


class MovieSummary(BaseModel):
    model_config = ConfigDict(strict=False, extra="ignore")

    tmdb_id: int = Field(..., alias="id")
    title: str
    overview: str | None = None
    release_date: str | None = None
    poster_path: str | None = None
    backdrop_path: str | None = None
    original_language: str | None = None
    vote_average: float | None = None
    vote_count: int | None = None


class MovieSearchResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    page: int
    results: list[MovieSummary]
    total_pages: int
    total_results: int


class MovieDetail(BaseModel):
    model_config = ConfigDict(strict=True, from_attributes=True)

    id: uuid.UUID
    tmdb_id: int
    title: str
    overview: str | None = None
    release_date: date | None = None
    poster_path: str | None = None
    backdrop_path: str | None = None
    genres: list[dict[str, Any]] = []
    runtime_minutes: int | None = None
    tmdb_rating: Decimal | None = None
    tmdb_vote_count: int | None = None
    original_language: str | None = None
    cached_at: datetime


class GenresResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    genres: list[MovieGenre]

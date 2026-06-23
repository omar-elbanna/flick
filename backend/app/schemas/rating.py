"""Rating schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.utils.sanitize import sanitize_text


class CreateRatingRequest(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    tmdb_id: int = Field(..., ge=1)
    score: int = Field(..., ge=1, le=5)
    review: str | None = Field(default=None, max_length=500)

    @field_validator("review")
    @classmethod
    def _sanitize_review(cls, v: str | None) -> str | None:
        return sanitize_text(v, max_length=500)


class RatingResponse(BaseModel):
    model_config = ConfigDict(strict=True, from_attributes=True)

    id: uuid.UUID
    movie_id: uuid.UUID
    tmdb_id: int
    movie_title: str
    poster_path: str | None = None
    score: int
    review: str | None = None
    created_at: datetime
    updated_at: datetime


class PaginatedRatings(BaseModel):
    model_config = ConfigDict(strict=True)

    items: list[RatingResponse]
    page: int
    page_size: int
    total: int

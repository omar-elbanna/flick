"""Recommendation request and response schemas."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.utils.sanitize import sanitize_required


class MoodRequest(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    mood: str = Field(..., min_length=2, max_length=200)

    @field_validator("mood")
    @classmethod
    def _sanitize(cls, v: str) -> str:
        return sanitize_required(v, max_length=200)


class RecommendedMovie(BaseModel):
    model_config = ConfigDict(strict=True)

    tmdb_id: int
    title: str
    overview: str | None = None
    poster_path: str | None = None
    release_date: str | None = None
    reasoning: str


class RecommendationsResponse(BaseModel):
    model_config = ConfigDict(strict=True)

    recommendations: list[RecommendedMovie]
    cached: bool = False

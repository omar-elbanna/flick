"""Movie service — fetch from TMDB and cache to the database."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.movie import Movie
from app.utils.tmdb_client import get_movie_detail

log = structlog.get_logger(__name__)


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def _to_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value)).quantize(Decimal("0.1"))
    except Exception:
        return None


async def fetch_and_cache_movie(tmdb_id: int, db: AsyncSession) -> Movie:
    """Return a Movie row by tmdb_id, fetching from TMDB if not cached."""

    existing = (
        await db.execute(select(Movie).where(Movie.tmdb_id == tmdb_id))
    ).scalar_one_or_none()

    if existing is not None:
        age = datetime.now(tz=timezone.utc) - existing.cached_at
        if age.total_seconds() < 86400:
            return existing

    data = await get_movie_detail(tmdb_id)
    return await _upsert_from_payload(db, data, existing)


async def _upsert_from_payload(
    db: AsyncSession,
    data: dict[str, Any],
    existing: Movie | None,
) -> Movie:
    genres = data.get("genres") or []
    if existing is None:
        movie = Movie(
            id=uuid.uuid4(),
            tmdb_id=int(data["id"]),
            title=str(data.get("title") or data.get("name") or "Untitled")[:500],
            overview=data.get("overview"),
            release_date=_parse_date(data.get("release_date")),
            poster_path=data.get("poster_path"),
            backdrop_path=data.get("backdrop_path"),
            genres=[{"id": g["id"], "name": g["name"]} for g in genres if "id" in g],
            runtime_minutes=data.get("runtime"),
            tmdb_rating=_to_decimal(data.get("vote_average")),
            tmdb_vote_count=int(data.get("vote_count") or 0),
            original_language=data.get("original_language"),
            cached_at=datetime.now(tz=timezone.utc),
        )
        db.add(movie)
    else:
        movie = existing
        movie.title = str(data.get("title") or movie.title)[:500]
        movie.overview = data.get("overview", movie.overview)
        movie.release_date = _parse_date(data.get("release_date")) or movie.release_date
        movie.poster_path = data.get("poster_path", movie.poster_path)
        movie.backdrop_path = data.get("backdrop_path", movie.backdrop_path)
        movie.genres = [
            {"id": g["id"], "name": g["name"]} for g in genres if "id" in g
        ] or movie.genres
        movie.runtime_minutes = data.get("runtime", movie.runtime_minutes)
        movie.tmdb_rating = _to_decimal(data.get("vote_average")) or movie.tmdb_rating
        movie.tmdb_vote_count = int(data.get("vote_count") or movie.tmdb_vote_count or 0)
        movie.original_language = data.get(
            "original_language", movie.original_language
        )
        movie.cached_at = datetime.now(tz=timezone.utc)
    await db.flush()
    await db.commit()
    return movie

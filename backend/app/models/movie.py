"""Cached movie metadata from TMDB."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import JSON, Date, DateTime, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

# Portable JSON: stays JSONB on Postgres for indexing power, falls back to JSON
# on SQLite so tests can run without a Postgres dependency.
_JsonType = JSON().with_variant(JSONB(), "postgresql")


class Movie(Base):
    __tablename__ = "movies"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tmdb_id: Mapped[int] = mapped_column(
        Integer, unique=True, nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    overview: Mapped[str | None] = mapped_column(Text, nullable=True)
    release_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    poster_path: Mapped[str | None] = mapped_column(String(300), nullable=True)
    backdrop_path: Mapped[str | None] = mapped_column(String(300), nullable=True)
    genres: Mapped[list[dict[str, Any]]] = mapped_column(
        _JsonType, nullable=False, default=list
    )
    runtime_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tmdb_rating: Mapped[Decimal | None] = mapped_column(Numeric(3, 1), nullable=True)
    tmdb_vote_count: Mapped[int | None] = mapped_column(Integer, default=0)
    original_language: Mapped[str | None] = mapped_column(String(10), nullable=True)
    cached_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

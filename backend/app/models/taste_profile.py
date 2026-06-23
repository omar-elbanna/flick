"""Aggregated taste profile per user — used to seed recommendations."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, Numeric
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

_JsonType = JSON().with_variant(JSONB(), "postgresql")

from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User


class UserTasteProfile(Base):
    __tablename__ = "user_taste_profiles"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    genre_weights: Mapped[dict[str, float]] = mapped_column(
        _JsonType, nullable=False, default=dict
    )
    avg_rating: Mapped[Decimal | None] = mapped_column(Numeric(3, 2), nullable=True)
    total_ratings: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    preferred_languages: Mapped[list[str]] = mapped_column(
        _JsonType, default=list, nullable=False
    )
    last_computed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    user: Mapped[User] = relationship(back_populates="taste_profile")

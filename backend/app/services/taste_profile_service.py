"""Compute and persist user taste profiles from their rating history."""

from __future__ import annotations

import uuid
from collections import Counter, defaultdict
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.movie import Movie
from app.models.rating import Rating
from app.models.taste_profile import UserTasteProfile

log = structlog.get_logger(__name__)


async def compute_taste_profile(user_id: uuid.UUID, db: AsyncSession) -> UserTasteProfile:
    """Recompute the taste profile for a user from their ratings.

    Genre weights are derived from rated movies: each rating contributes a
    weight per genre proportional to (score / 5). Weights are normalized to
    [0, 1] by dividing each by the maximum.
    """

    stmt = (
        select(Rating, Movie)
        .join(Movie, Rating.movie_id == Movie.id)
        .where(Rating.user_id == user_id)
    )
    rows = (await db.execute(stmt)).all()

    weights: dict[str, float] = defaultdict(float)
    language_counter: Counter[str] = Counter()
    total = 0
    score_sum = 0

    for rating, movie in rows:
        weight = rating.score / 5.0
        for genre in movie.genres or []:
            gid = str(genre.get("id")) if isinstance(genre, dict) else None
            if gid:
                weights[gid] += weight
        if movie.original_language:
            language_counter[movie.original_language] += 1
        total += 1
        score_sum += rating.score

    normalized: dict[str, float] = {}
    if weights:
        max_w = max(weights.values())
        if max_w > 0:
            normalized = {gid: round(w / max_w, 4) for gid, w in weights.items()}

    preferred_languages = [lang for lang, _ in language_counter.most_common(3)]
    avg = Decimal(score_sum) / Decimal(total) if total else None
    if avg is not None:
        avg = avg.quantize(Decimal("0.01"))

    profile = (
        await db.execute(
            select(UserTasteProfile).where(UserTasteProfile.user_id == user_id)
        )
    ).scalar_one_or_none()
    now = datetime.now(tz=UTC)
    if profile is None:
        profile = UserTasteProfile(
            user_id=user_id,
            genre_weights=normalized,
            avg_rating=avg,
            total_ratings=total,
            preferred_languages=preferred_languages,
            last_computed_at=now,
        )
        db.add(profile)
    else:
        profile.genre_weights = normalized
        profile.avg_rating = avg
        profile.total_ratings = total
        profile.preferred_languages = preferred_languages
        profile.last_computed_at = now

    await db.flush()
    log.info("taste.profile_computed", user_id=str(user_id), total_ratings=total)
    return profile


def aggregate_group_taste(profiles: list[UserTasteProfile]) -> dict[str, float]:
    """Average genre_weights across a list of user taste profiles.

    Genres absent from a profile contribute 0 for that member.
    """

    if not profiles:
        return {}
    aggregate: dict[str, float] = defaultdict(float)
    member_count = len(profiles)
    for profile in profiles:
        for gid, weight in (profile.genre_weights or {}).items():
            aggregate[gid] += float(weight)
    return {gid: round(total / member_count, 4) for gid, total in aggregate.items()}


def _placeholder_for_type_checkers() -> dict[str, Any]:
    return {}

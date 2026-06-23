"""AI recommendation endpoints."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import _get_session, get_current_user
from app.models.user import User
from app.schemas.recommendation import (
    MoodRequest,
    RecommendationsResponse,
)
from app.services.recommendation_service import (
    get_mood_recommendations,
    get_personal_recommendations,
)
from app.utils.rate_limit import limiter
from app.utils.tmdb_client import get_similar, get_tmdb_recommendations

router = APIRouter()


@router.post("/personal", response_model=RecommendationsResponse)
@limiter.limit("10/minute")
async def personal(
    request: Request,
    db: Annotated[AsyncSession, Depends(_get_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> RecommendationsResponse:
    return await get_personal_recommendations(current_user.id, db)


@router.post("/mood", response_model=RecommendationsResponse)
@limiter.limit("10/minute")
async def mood(
    request: Request,
    payload: MoodRequest,
    db: Annotated[AsyncSession, Depends(_get_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> RecommendationsResponse:
    return await get_mood_recommendations(current_user.id, payload.mood, db)


@router.get("/similar/{tmdb_id}")
@limiter.limit("30/minute")
async def similar(
    request: Request,
    tmdb_id: int,
    _user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    """Return TMDB recommendations first (high quality), then /similar as fallback.

    TMDB's /similar is keyword-matched and notoriously noisy; /recommendations
    is curated from user behavior signals. We merge both, dedup, and prefer the
    recommendations ordering.
    """

    primary_results: list[dict[str, Any]] = []
    seen_ids: set[int] = set()
    try:
        primary = await get_tmdb_recommendations(tmdb_id)
        for m in primary.get("results", []) or []:
            mid = m.get("id")
            if isinstance(mid, int) and mid not in seen_ids:
                seen_ids.add(mid)
                primary_results.append(m)
    except Exception:
        pass

    # Top up with /similar only if we have very few recommendations.
    if len(primary_results) < 12:
        try:
            fallback = await get_similar(tmdb_id)
            for m in fallback.get("results", []) or []:
                mid = m.get("id")
                if isinstance(mid, int) and mid not in seen_ids:
                    seen_ids.add(mid)
                    primary_results.append(m)
                    if len(primary_results) >= 20:
                        break
        except Exception:
            pass

    return {
        "page": 1,
        "results": primary_results[:20],
        "total_pages": 1,
        "total_results": len(primary_results),
    }

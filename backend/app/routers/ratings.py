"""Rating CRUD endpoints."""

from __future__ import annotations

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import _get_session, get_current_user
from app.models.movie import Movie
from app.models.rating import Rating
from app.models.user import User
from app.schemas.rating import CreateRatingRequest, PaginatedRatings, RatingResponse
from app.services.movie_service import fetch_and_cache_movie
from app.services.taste_profile_service import compute_taste_profile
from app.utils.rate_limit import limiter

router = APIRouter()


def _to_response(rating: Rating, movie: Movie) -> RatingResponse:
    return RatingResponse(
        id=rating.id,
        movie_id=rating.movie_id,
        tmdb_id=movie.tmdb_id,
        movie_title=movie.title,
        poster_path=movie.poster_path,
        score=rating.score,
        review=rating.review,
        created_at=rating.created_at,
        updated_at=rating.updated_at,
    )


@router.post(
    "/ratings",
    response_model=RatingResponse,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("60/minute")
async def upsert_rating(
    request: Request,
    payload: CreateRatingRequest,
    db: Annotated[AsyncSession, Depends(_get_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> RatingResponse:
    movie = await fetch_and_cache_movie(payload.tmdb_id, db)
    existing = (
        await db.execute(
            select(Rating).where(
                Rating.user_id == current_user.id, Rating.movie_id == movie.id
            )
        )
    ).scalar_one_or_none()
    if existing is None:
        rating = Rating(
            user_id=current_user.id,
            movie_id=movie.id,
            score=payload.score,
            review=payload.review,
        )
        db.add(rating)
    else:
        existing.score = payload.score
        existing.review = payload.review
        rating = existing
    await db.flush()
    await compute_taste_profile(current_user.id, db)
    await db.commit()
    await db.refresh(rating)
    return _to_response(rating, movie)


@router.delete("/ratings/{rating_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("60/minute")
async def delete_rating(
    request: Request,
    rating_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(_get_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> None:
    rating = await db.get(Rating, rating_id)
    if rating is None or rating.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": "Rating not found.", "code": "RATING_NOT_FOUND"},
        )
    await db.delete(rating)
    await db.flush()
    await compute_taste_profile(current_user.id, db)
    await db.commit()


@router.get("/users/me/ratings", response_model=PaginatedRatings)
@limiter.limit("60/minute")
async def list_my_ratings(
    request: Request,
    db: Annotated[AsyncSession, Depends(_get_session)],
    current_user: Annotated[User, Depends(get_current_user)],
    page: Annotated[int, Query(ge=1, le=1000)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    sort: Annotated[Literal["recent", "score_desc", "score_asc"], Query()] = "recent",
) -> PaginatedRatings:
    order_by = {
        "recent": desc(Rating.created_at),
        "score_desc": desc(Rating.score),
        "score_asc": Rating.score.asc(),
    }[sort]

    total = (
        await db.execute(
            select(func.count(Rating.id)).where(Rating.user_id == current_user.id)
        )
    ).scalar_one()

    stmt = (
        select(Rating, Movie)
        .join(Movie, Movie.id == Rating.movie_id)
        .where(Rating.user_id == current_user.id)
        .order_by(order_by)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = (await db.execute(stmt)).all()
    items = [_to_response(rating, movie) for rating, movie in rows]
    return PaginatedRatings(items=items, page=page, page_size=page_size, total=total)

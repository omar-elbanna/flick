"""Personal, mood, and group movie recommendations powered by OpenAI."""

from __future__ import annotations

import asyncio
import json
import re
import uuid
from typing import Any

import structlog
from fastapi import HTTPException, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.movie import Movie
from app.models.rating import Rating
from app.models.taste_profile import UserTasteProfile
from app.schemas.recommendation import RecommendationsResponse, RecommendedMovie
from app.services.movie_service import fetch_and_cache_movie
from app.utils.openai_client import OpenAIError, call_with_retry
from app.utils.redis_client import cache_get, cache_set
from app.utils.tmdb_client import search_movies

log = structlog.get_logger(__name__)

PERSONAL_CACHE_TTL = 15 * 60
MAX_RESULTS = 20

_TITLE_STRIP_RE = re.compile(r"[^a-z0-9]+")


def _normalize_title(s: str) -> set[str]:
    """Lowercase, strip punctuation, return the set of word tokens."""

    cleaned = _TITLE_STRIP_RE.sub(" ", s.lower()).strip()
    return {w for w in cleaned.split() if len(w) > 1}


def _titles_match(claimed: str, actual: str, *, threshold: float = 0.5) -> bool:
    """True if the two titles share enough word tokens to be the same film.

    Uses Jaccard similarity over normalized word sets. "The Matrix" vs "Matrix"
    matches; "Spirited Away" vs "Amazing Spider-Man" does not.
    """

    a, b = _normalize_title(claimed), _normalize_title(actual)
    if not a or not b:
        return False
    overlap = len(a & b)
    union = len(a | b)
    return (overlap / union) >= threshold if union else False


async def _genre_lookup(weights: dict[str, float]) -> dict[str, str]:
    """Best-effort TMDB-id → genre-name mapping from local movies."""

    return {}


async def _recent_history(
    user_id: uuid.UUID, db: AsyncSession, limit: int = 20
) -> list[dict[str, Any]]:
    rows = (
        await db.execute(
            select(Rating, Movie)
            .join(Movie, Movie.id == Rating.movie_id)
            .where(Rating.user_id == user_id)
            .order_by(desc(Rating.created_at))
            .limit(limit)
        )
    ).all()
    return [
        {
            "title": movie.title,
            "score": rating.score,
            "genres": [g.get("name") for g in (movie.genres or []) if g.get("name")],
        }
        for rating, movie in rows
    ]


def _build_personal_prompt(
    profile: UserTasteProfile | None, history: list[dict[str, Any]]
) -> list[dict[str, str]]:
    genre_weights = profile.genre_weights if profile else {}
    avg = float(profile.avg_rating) if profile and profile.avg_rating else None
    payload = {
        "genre_weights_tmdb_ids": genre_weights,
        "preferred_languages": profile.preferred_languages if profile else [],
        "avg_rating": avg,
        "recent_history": history,
    }
    system = (
        "You are a film recommender for the Flick app. You will be given a user's "
        "taste profile and recent rating history. Return 20 movie recommendations as "
        "JSON, ordered from most to least confident. Do NOT recommend any title that "
        "already appears in the user's history. Include the release year so we can "
        "disambiguate remakes. Reply with valid JSON ONLY in this exact shape:\n"
        '{"recommendations":[{"title":str,"year":int,"reasoning":str}]}\n'
        "No prose, no markdown fences, no extra fields."
    )
    user = (
        "Recommend 20 movies for this user. Profile and history:\n"
        + json.dumps(payload, indent=2)
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def _build_mood_prompt(
    mood: str,
    profile: UserTasteProfile | None,
    history: list[dict[str, Any]],
) -> list[dict[str, str]]:
    payload = {
        "mood_or_query": mood,
        "genre_weights_tmdb_ids": profile.genre_weights if profile else {},
        "preferred_languages": profile.preferred_languages if profile else [],
        "recent_history": history,
    }
    system = (
        "You are a film recommender. The user's MOOD may be a feeling (\"cozy rainy "
        "night\"), a genre (\"high-energy action\"), a studio/franchise (\"Studio "
        "Ghibli\", \"Marvel\", \"A24\"), or a director (\"Wes Anderson\"). Return 20 "
        "movies ordered from MOST to LEAST relevant. Never invent or guess — only "
        "include films whose connection to the prompt you are confident about. Include "
        "the release year so we can disambiguate remakes. Reply with valid JSON ONLY "
        'in this exact shape: {"recommendations":[{"title":str,"year":int,"reasoning":str}]}.'
    )
    user = (
        "Recommend up to 20 movies. Context:\n" + json.dumps(payload, indent=2)
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def _build_group_prompt(
    group_vector: dict[str, float],
    collective_history: list[dict[str, Any]],
) -> list[dict[str, str]]:
    payload = {
        "group_taste_vector_tmdb_genre_ids": group_vector,
        "collective_recent_history": collective_history,
    }
    system = (
        "You recommend movies for a GROUP of friends watching together. Given their "
        "aggregated taste vector (averaged genre affinities) and recent watch history, "
        "pick 5 movies that maximize consensus enjoyment — high overlap with shared "
        "preferences, broadly appealing, no titles already in the history. Include the "
        "release year so we can disambiguate remakes. Reply with valid JSON ONLY: "
        '{"recommendations":[{"title":str,"year":int,"reasoning":str}]}.'
    )
    user = "Recommend 5 group movies. Context:\n" + json.dumps(payload, indent=2)
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


async def _resolve_recommendation(
    claimed_title: str,
    claimed_year: int | None,
    db: AsyncSession,
) -> Movie | None:
    """Find the real TMDB movie for a title the AI returned.

    We do NOT trust LLM-supplied tmdb_ids — gpt-4o-mini hallucinates them
    constantly. Instead we search TMDB by title and pick the best hit, using
    the optional year hint to disambiguate remakes.
    """

    try:
        search = await search_movies(claimed_title, 1)
    except HTTPException:
        return None
    results = (search.get("results") or [])[:8]
    if not results:
        return None

    # Score every result, prefer title match + year match.
    best: tuple[float, dict[str, Any]] | None = None
    for r in results:
        rt = str(r.get("title") or "")
        if not _titles_match(claimed_title, rt):
            continue
        score = float(r.get("popularity") or 0)
        if claimed_year and isinstance(r.get("release_date"), str):
            try:
                ry = int(r["release_date"][:4])
                if ry == claimed_year:
                    score += 10_000  # exact year crushes everything else
                elif abs(ry - claimed_year) <= 1:
                    score += 1_000
            except ValueError:
                pass
        if best is None or score > best[0]:
            best = (score, r)

    if best is None:
        return None
    pick_id = best[1].get("id")
    if not isinstance(pick_id, int):
        return None
    try:
        return await fetch_and_cache_movie(pick_id, db)
    except HTTPException:
        return None


async def _materialize_recommendations(
    raw: dict[str, Any],
    db: AsyncSession,
) -> list[RecommendedMovie]:
    items = raw.get("recommendations")
    if not isinstance(items, list) or not items:
        raise OpenAIError("AI returned no recommendations.")

    # Build the list of (claimed_title, year, reasoning) entries, preserving
    # the AI's ordering.
    queue: list[tuple[str, int | None, str]] = []
    for entry in items[: MAX_RESULTS * 2]:
        try:
            claimed_title = str(entry.get("title") or "").strip()
            year_raw = entry.get("year")
            year = int(year_raw) if isinstance(year_raw, (int, str)) and str(year_raw).isdigit() else None
            reasoning = str(entry.get("reasoning") or "").strip() or "Recommended for you."
        except (TypeError, ValueError):
            continue
        if not claimed_title:
            continue
        queue.append((claimed_title, year, reasoning))

    if not queue:
        raise OpenAIError("AI returned no usable titles.")

    # Resolve all titles in parallel via TMDB search.
    resolved = await asyncio.gather(
        *(_resolve_recommendation(title, year, db) for title, year, _ in queue),
        return_exceptions=True,
    )
    out: list[RecommendedMovie] = []
    seen_ids: set[int] = set()
    for (_title, _year, reasoning), result in zip(queue, resolved):
        if isinstance(result, BaseException) or result is None:
            continue
        movie = result
        if movie.tmdb_id in seen_ids:
            continue
        seen_ids.add(movie.tmdb_id)
        out.append(
            RecommendedMovie(
                tmdb_id=movie.tmdb_id,
                title=movie.title,
                overview=movie.overview,
                poster_path=movie.poster_path,
                release_date=movie.release_date.isoformat() if movie.release_date else None,
                reasoning=reasoning,
            )
        )
        if len(out) >= MAX_RESULTS:
            break

    if not out:
        raise OpenAIError(
            "Could not find any of the AI's picks on TMDB. Try a different prompt."
        )
    return out


async def get_personal_recommendations(
    user_id: uuid.UUID, db: AsyncSession
) -> RecommendationsResponse:
    cache_key = f"reco:personal:{user_id}"
    cached = await cache_get(cache_key)
    if cached:
        return RecommendationsResponse(
            recommendations=[RecommendedMovie(**r) for r in cached["recommendations"]],
            cached=True,
        )

    profile = (
        await db.execute(
            select(UserTasteProfile).where(UserTasteProfile.user_id == user_id)
        )
    ).scalar_one_or_none()
    history = await _recent_history(user_id, db)
    if not history:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "detail": "Rate at least one movie before requesting recommendations.",
                "code": "NO_RATINGS",
            },
        )

    messages = _build_personal_prompt(profile, history)
    raw = await call_with_retry(messages, json_response=True)
    recommendations = await _materialize_recommendations(raw, db)

    payload = {"recommendations": [r.model_dump() for r in recommendations]}
    await cache_set(cache_key, payload, PERSONAL_CACHE_TTL)
    return RecommendationsResponse(recommendations=recommendations, cached=False)


async def get_mood_recommendations(
    user_id: uuid.UUID, mood: str, db: AsyncSession
) -> RecommendationsResponse:
    profile = (
        await db.execute(
            select(UserTasteProfile).where(UserTasteProfile.user_id == user_id)
        )
    ).scalar_one_or_none()
    history = await _recent_history(user_id, db, limit=15)
    messages = _build_mood_prompt(mood, profile, history)
    raw = await call_with_retry(messages, json_response=True)
    recommendations = await _materialize_recommendations(raw, db)
    return RecommendationsResponse(recommendations=recommendations, cached=False)


async def get_group_recommendations(
    group_vector: dict[str, float],
    collective_history: list[dict[str, Any]],
    db: AsyncSession,
) -> list[RecommendedMovie]:
    messages = _build_group_prompt(group_vector, collective_history)
    raw = await call_with_retry(messages, json_response=True)
    return await _materialize_recommendations(raw, db)


async def invalidate_personal_cache(user_id: uuid.UUID) -> None:
    from app.utils.redis_client import cache_delete

    await cache_delete(f"reco:personal:{user_id}")

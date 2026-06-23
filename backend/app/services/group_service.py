"""Group, membership, and session lifecycle logic."""

from __future__ import annotations

import asyncio
import secrets
import string
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

import structlog
from fastapi import HTTPException, status
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.group import (
    Group,
    GroupMember,
    GroupMemberRole,
    GroupSession,
    GroupSessionStatus,
    SessionVote,
    VoteChoice,
)
from app.models.movie import Movie
from app.models.rating import Rating
from app.models.taste_profile import UserTasteProfile
from app.models.user import User
from app.schemas.group import (
    GroupDetail,
    GroupMemberResponse,
    GroupSessionResponse,
    GroupSummary,
    SessionCandidate,
)
from app.services.recommendation_service import get_group_recommendations
from app.services.taste_profile_service import aggregate_group_taste

log = structlog.get_logger(__name__)

MIN_RATINGS_PER_MEMBER = 5
SESSION_TIMEOUT_SECONDS = 5 * 60
_VOTE_POINTS: dict[VoteChoice, int] = {
    VoteChoice.YES: 2,
    VoteChoice.MAYBE: 1,
    VoteChoice.NO: 0,
}


def _generate_invite_code() -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(8))


async def create_group(db: AsyncSession, creator: User, name: str) -> Group:
    for _ in range(5):
        code = _generate_invite_code()
        exists = (
            await db.execute(select(Group).where(Group.invite_code == code))
        ).scalar_one_or_none()
        if exists is None:
            break
    else:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"detail": "Could not allocate invite code.", "code": "INVITE_CODE_EXHAUSTED"},
        )
    group = Group(name=name, created_by=creator.id, invite_code=code)
    db.add(group)
    await db.flush()
    db.add(GroupMember(group_id=group.id, user_id=creator.id, role=GroupMemberRole.OWNER))
    await db.commit()
    await db.refresh(group)
    return group


async def list_user_groups(db: AsyncSession, user_id: uuid.UUID) -> list[GroupSummary]:
    member_count_sq = (
        select(GroupMember.group_id, func.count(GroupMember.id).label("c"))
        .group_by(GroupMember.group_id)
        .subquery()
    )
    stmt = (
        select(Group, GroupMember.role, member_count_sq.c.c)
        .join(GroupMember, GroupMember.group_id == Group.id)
        .join(member_count_sq, member_count_sq.c.group_id == Group.id)
        .where(GroupMember.user_id == user_id, Group.is_active.is_(True))
        .order_by(desc(Group.created_at))
    )
    rows = (await db.execute(stmt)).all()
    return [
        GroupSummary(
            id=group.id,
            name=group.name,
            invite_code=group.invite_code,
            created_at=group.created_at,
            member_count=int(count),
            role=role,
        )
        for group, role, count in rows
    ]


async def get_group_detail(
    db: AsyncSession, user_id: uuid.UUID, group_id: uuid.UUID
) -> GroupDetail:
    group = (
        await db.execute(
            select(Group)
            .options(selectinload(Group.members).selectinload(GroupMember.user))
            .where(Group.id == group_id)
        )
    ).scalar_one_or_none()
    if group is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": "Group not found.", "code": "GROUP_NOT_FOUND"},
        )
    if not any(m.user_id == user_id for m in group.members):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"detail": "Not a group member.", "code": "NOT_MEMBER"},
        )
    members = [
        GroupMemberResponse(
            user_id=m.user_id,
            display_name=m.user.display_name,
            avatar_url=m.user.avatar_url,
            role=m.role,
            joined_at=m.joined_at,
        )
        for m in group.members
    ]
    return GroupDetail(
        id=group.id,
        name=group.name,
        invite_code=group.invite_code,
        created_by=group.created_by,
        created_at=group.created_at,
        is_active=group.is_active,
        members=members,
    )


async def join_group_by_code(
    db: AsyncSession, user: User, invite_code: str
) -> GroupDetail:
    group = (
        await db.execute(
            select(Group).where(Group.invite_code == invite_code.upper(), Group.is_active.is_(True))
        )
    ).scalar_one_or_none()
    if group is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": "Invite code not found.", "code": "INVITE_NOT_FOUND"},
        )
    existing = (
        await db.execute(
            select(GroupMember).where(
                GroupMember.group_id == group.id, GroupMember.user_id == user.id
            )
        )
    ).scalar_one_or_none()
    if existing is None:
        db.add(
            GroupMember(group_id=group.id, user_id=user.id, role=GroupMemberRole.MEMBER)
        )
        await db.commit()
    return await get_group_detail(db, user.id, group.id)


async def leave_group(db: AsyncSession, user: User, group_id: uuid.UUID) -> None:
    member = (
        await db.execute(
            select(GroupMember).where(
                GroupMember.group_id == group_id, GroupMember.user_id == user.id
            )
        )
    ).scalar_one_or_none()
    if member is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": "Not a member.", "code": "NOT_MEMBER"},
        )
    other_count = (
        await db.execute(
            select(func.count(GroupMember.id)).where(
                GroupMember.group_id == group_id, GroupMember.user_id != user.id
            )
        )
    ).scalar_one()
    if member.role == GroupMemberRole.OWNER and other_count > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "detail": "Owner cannot leave while other members remain.",
                "code": "OWNER_CANNOT_LEAVE",
            },
        )
    await db.delete(member)
    await db.commit()


async def list_group_members(
    db: AsyncSession, user_id: uuid.UUID, group_id: uuid.UUID
) -> list[GroupMemberResponse]:
    detail = await get_group_detail(db, user_id, group_id)
    return detail.members


# --- Session flow --------------------------------------------------------------


async def _ensure_member(
    db: AsyncSession, user_id: uuid.UUID, group_id: uuid.UUID
) -> None:
    member = (
        await db.execute(
            select(GroupMember).where(
                GroupMember.group_id == group_id, GroupMember.user_id == user_id
            )
        )
    ).scalar_one_or_none()
    if member is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"detail": "Not a group member.", "code": "NOT_MEMBER"},
        )


async def _collect_member_history(
    db: AsyncSession, member_ids: list[uuid.UUID], per_user_limit: int = 20
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for uid in member_ids:
        rows = (
            await db.execute(
                select(Rating, Movie)
                .join(Movie, Movie.id == Rating.movie_id)
                .where(Rating.user_id == uid)
                .order_by(desc(Rating.created_at))
                .limit(per_user_limit)
            )
        ).all()
        for rating, movie in rows:
            out.append(
                {
                    "title": movie.title,
                    "score": rating.score,
                    "genres": [g.get("name") for g in (movie.genres or []) if g.get("name")],
                }
            )
    return out


async def start_session(
    db: AsyncSession,
    starter: User,
    group_id: uuid.UUID,
) -> tuple[GroupSession, list[SessionCandidate]]:
    await _ensure_member(db, starter.id, group_id)
    members = (
        await db.execute(
            select(GroupMember).where(GroupMember.group_id == group_id)
        )
    ).scalars().all()
    if not members:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": "Group has no members.", "code": "EMPTY_GROUP"},
        )

    insufficient: list[str] = []
    for m in members:
        count = (
            await db.execute(
                select(func.count(Rating.id)).where(Rating.user_id == m.user_id)
            )
        ).scalar_one()
        if count < MIN_RATINGS_PER_MEMBER:
            insufficient.append(str(m.user_id))
    if insufficient:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "detail": (
                    f"Every member needs at least {MIN_RATINGS_PER_MEMBER} ratings "
                    "before starting a session."
                ),
                "code": "INSUFFICIENT_RATINGS",
                "members_needing_ratings": insufficient,
            },
        )

    profiles = (
        await db.execute(
            select(UserTasteProfile).where(
                UserTasteProfile.user_id.in_([m.user_id for m in members])
            )
        )
    ).scalars().all()
    group_vector = aggregate_group_taste(list(profiles))
    history = await _collect_member_history(db, [m.user_id for m in members])

    session = GroupSession(
        group_id=group_id,
        started_by=starter.id,
        status=GroupSessionStatus.ACTIVE,
    )
    db.add(session)
    await db.flush()

    recommended = await get_group_recommendations(group_vector, history, db)
    candidates: list[SessionCandidate] = []
    for r in recommended:
        movie = (
            await db.execute(select(Movie).where(Movie.tmdb_id == r.tmdb_id))
        ).scalar_one_or_none()
        if movie is None:
            continue
        candidates.append(
            SessionCandidate(
                tmdb_id=r.tmdb_id,
                movie_id=movie.id,
                title=r.title,
                poster_path=r.poster_path,
                overview=r.overview,
                reasoning=r.reasoning,
            )
        )
    if not candidates:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "detail": "Could not generate candidate movies.",
                "code": "NO_CANDIDATES",
            },
        )

    # Persist candidates as zero-vote placeholders so we can rebuild on reconnect.
    # We use Redis for ephemeral candidate cache so reconnecting clients can hydrate.
    from app.utils.redis_client import cache_set

    await cache_set(
        f"session:{session.id}:candidates",
        [c.model_dump(mode="json") for c in candidates],
        ttl_seconds=24 * 3600,
    )
    await db.commit()
    log.info(
        "session.started",
        session_id=str(session.id),
        group_id=str(group_id),
        candidate_count=len(candidates),
    )
    return session, candidates


async def get_session_candidates(session_id: uuid.UUID) -> list[SessionCandidate]:
    from app.utils.redis_client import cache_get

    raw = await cache_get(f"session:{session_id}:candidates")
    if not raw:
        return []
    return [SessionCandidate(**c) for c in raw]


async def reroll_session_candidates(
    db: AsyncSession,
    requester: User,
    group_id: uuid.UUID,
    session_id: uuid.UUID,
) -> list[SessionCandidate]:
    """Replace the active session's candidates with a fresh AI-picked set.

    Wipes existing votes for the session (they were cast against the old
    candidate set, so they wouldn't make sense against the new one).
    """

    await _ensure_member(db, requester.id, group_id)
    session = await db.get(GroupSession, session_id)
    if session is None or session.group_id != group_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": "Session not found.", "code": "SESSION_NOT_FOUND"},
        )
    if session.status != GroupSessionStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"detail": "Session is not active.", "code": "SESSION_INACTIVE"},
        )

    members = (
        await db.execute(
            select(GroupMember).where(GroupMember.group_id == group_id)
        )
    ).scalars().all()
    profiles = (
        await db.execute(
            select(UserTasteProfile).where(
                UserTasteProfile.user_id.in_([m.user_id for m in members])
            )
        )
    ).scalars().all()
    group_vector = aggregate_group_taste(list(profiles))
    history = await _collect_member_history(db, [m.user_id for m in members])

    # Add the existing candidates' titles to the history so the AI is asked not
    # to repeat them.
    existing = await get_session_candidates(session_id)
    for c in existing:
        history.append({"title": c.title, "score": 0, "genres": []})

    recommended = await get_group_recommendations(group_vector, history, db)
    new_candidates: list[SessionCandidate] = []
    seen_existing = {c.tmdb_id for c in existing}
    for r in recommended:
        if r.tmdb_id in seen_existing:
            continue
        movie = (
            await db.execute(select(Movie).where(Movie.tmdb_id == r.tmdb_id))
        ).scalar_one_or_none()
        if movie is None:
            continue
        new_candidates.append(
            SessionCandidate(
                tmdb_id=r.tmdb_id,
                movie_id=movie.id,
                title=r.title,
                poster_path=r.poster_path,
                overview=r.overview,
                reasoning=r.reasoning,
            )
        )
        if len(new_candidates) >= 5:
            break
    if not new_candidates:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "detail": "Could not generate new candidates.",
                "code": "NO_NEW_CANDIDATES",
            },
        )

    # Wipe stale votes; the old candidates are gone.
    await db.execute(
        SessionVote.__table__.delete().where(SessionVote.session_id == session_id)
    )

    from app.utils.redis_client import cache_set

    await cache_set(
        f"session:{session_id}:candidates",
        [c.model_dump(mode="json") for c in new_candidates],
        ttl_seconds=24 * 3600,
    )
    await db.commit()
    log.info(
        "session.rerolled",
        session_id=str(session_id),
        new_count=len(new_candidates),
    )
    return new_candidates


async def cast_vote(
    db: AsyncSession,
    voter: User,
    group_id: uuid.UUID,
    session_id: uuid.UUID,
    movie_id: uuid.UUID,
    vote: VoteChoice,
) -> tuple[GroupSession, dict[str, dict[str, int]], bool]:
    await _ensure_member(db, voter.id, group_id)
    session = await db.get(GroupSession, session_id)
    if session is None or session.group_id != group_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": "Session not found.", "code": "SESSION_NOT_FOUND"},
        )
    if session.status != GroupSessionStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"detail": "Session is not active.", "code": "SESSION_INACTIVE"},
        )

    existing = (
        await db.execute(
            select(SessionVote).where(
                SessionVote.session_id == session_id,
                SessionVote.user_id == voter.id,
                SessionVote.movie_id == movie_id,
            )
        )
    ).scalar_one_or_none()
    if existing is None:
        db.add(
            SessionVote(
                session_id=session_id,
                user_id=voter.id,
                movie_id=movie_id,
                vote=vote,
            )
        )
    else:
        existing.vote = vote
    await db.flush()

    tally = await build_vote_tally(db, session_id)
    finished = await maybe_finalize_session(db, session)
    await db.commit()
    return session, tally, finished


async def build_vote_tally(
    db: AsyncSession, session_id: uuid.UUID
) -> dict[str, dict[str, int]]:
    rows = (
        await db.execute(
            select(SessionVote.movie_id, SessionVote.vote, func.count(SessionVote.id))
            .where(SessionVote.session_id == session_id)
            .group_by(SessionVote.movie_id, SessionVote.vote)
        )
    ).all()
    tally: dict[str, dict[str, int]] = defaultdict(
        lambda: {"yes": 0, "no": 0, "maybe": 0, "score": 0}
    )
    for movie_id, vote, count in rows:
        key = str(movie_id)
        vote_value = vote.value if isinstance(vote, VoteChoice) else str(vote)
        tally[key][vote_value] = int(count)
        tally[key]["score"] += int(count) * _VOTE_POINTS[VoteChoice(vote_value)]
    return dict(tally)


async def maybe_finalize_session(db: AsyncSession, session: GroupSession) -> bool:
    """Finalize the session if every member has voted on every candidate.

    Returns True if the session transitioned to completed.
    """

    candidates = await get_session_candidates(session.id)
    member_count = (
        await db.execute(
            select(func.count(GroupMember.id)).where(
                GroupMember.group_id == session.group_id
            )
        )
    ).scalar_one()
    vote_count = (
        await db.execute(
            select(func.count(SessionVote.id)).where(
                SessionVote.session_id == session.id
            )
        )
    ).scalar_one()
    expected = int(member_count) * len(candidates)
    if expected == 0 or vote_count < expected:
        return False

    winner_movie_id = await _resolve_winner(db, session.id)
    if winner_movie_id is None:
        return False
    session.recommended_movie_id = winner_movie_id
    session.status = GroupSessionStatus.COMPLETED
    session.completed_at = datetime.now(tz=timezone.utc)
    await db.flush()
    return True


async def _resolve_winner(
    db: AsyncSession, session_id: uuid.UUID
) -> uuid.UUID | None:
    tally = await build_vote_tally(db, session_id)
    if not tally:
        return None
    best_id, best_score = None, -1
    for movie_id, counts in tally.items():
        if counts["score"] > best_score:
            best_score = counts["score"]
            best_id = uuid.UUID(movie_id)
    return best_id


async def expire_session_if_overdue(db: AsyncSession, session_id: uuid.UUID) -> bool:
    session = await db.get(GroupSession, session_id)
    if session is None or session.status != GroupSessionStatus.ACTIVE:
        return False
    age = datetime.now(tz=timezone.utc) - session.started_at
    if age < timedelta(seconds=SESSION_TIMEOUT_SECONDS):
        return False
    winner = await _resolve_winner(db, session_id)
    if winner is not None:
        session.recommended_movie_id = winner
        session.status = GroupSessionStatus.COMPLETED
        session.completed_at = datetime.now(tz=timezone.utc)
    else:
        session.status = GroupSessionStatus.EXPIRED
        session.completed_at = datetime.now(tz=timezone.utc)
    await db.commit()
    return True


async def session_to_response(
    db: AsyncSession, session: GroupSession
) -> GroupSessionResponse:
    candidates = await get_session_candidates(session.id)
    winner_tmdb_id: int | None = None
    if session.recommended_movie_id is not None:
        movie = await db.get(Movie, session.recommended_movie_id)
        if movie is not None:
            winner_tmdb_id = movie.tmdb_id
    return GroupSessionResponse(
        id=session.id,
        group_id=session.group_id,
        status=session.status,
        started_by=session.started_by,
        started_at=session.started_at,
        completed_at=session.completed_at,
        candidates=candidates,
        winner_movie_id=session.recommended_movie_id,
        winner_tmdb_id=winner_tmdb_id,
    )


_session_timeout_tasks: dict[uuid.UUID, asyncio.Task[Any]] = {}


def schedule_session_timeout(session_id: uuid.UUID, coro_factory: Any) -> None:
    """Best-effort in-process timer — production should use a job queue."""

    if session_id in _session_timeout_tasks:
        return

    async def _runner() -> None:
        try:
            await asyncio.sleep(SESSION_TIMEOUT_SECONDS)
            await coro_factory()
        finally:
            _session_timeout_tasks.pop(session_id, None)

    _session_timeout_tasks[session_id] = asyncio.create_task(_runner())

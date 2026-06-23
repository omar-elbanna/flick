"""Group, membership, and session HTTP endpoints."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import _get_session, get_current_user
from app.models.group import GroupMemberRole, GroupSession
from app.models.user import User
from app.routers.websocket import (
    broadcast_session_completed,
    broadcast_session_started,
    broadcast_vote_cast,
    expire_and_broadcast,
)
from app.schemas.group import (
    CastVoteRequest,
    CreateGroupRequest,
    GroupDetail,
    GroupMemberResponse,
    GroupSessionResponse,
    GroupSummary,
    JoinGroupRequest,
    VoteResponse,
)
from app.services.group_service import (
    cast_vote,
    create_group,
    get_group_detail,
    join_group_by_code,
    leave_group,
    list_group_members,
    list_user_groups,
    reroll_session_candidates,
    schedule_session_timeout,
    session_to_response,
    start_session,
)
from app.utils.rate_limit import limiter

router = APIRouter()


@router.post(
    "", response_model=GroupSummary, status_code=status.HTTP_201_CREATED
)
@limiter.limit("30/minute")
async def create(
    request: Request,
    payload: CreateGroupRequest,
    db: Annotated[AsyncSession, Depends(_get_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> GroupSummary:
    group = await create_group(db, current_user, payload.name)
    return GroupSummary(
        id=group.id,
        name=group.name,
        invite_code=group.invite_code,
        created_at=group.created_at,
        member_count=1,
        role=GroupMemberRole.OWNER,
    )


@router.get("", response_model=list[GroupSummary])
@limiter.limit("60/minute")
async def list_groups(
    request: Request,
    db: Annotated[AsyncSession, Depends(_get_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[GroupSummary]:
    return await list_user_groups(db, current_user.id)


@router.get("/{group_id}", response_model=GroupDetail)
@limiter.limit("60/minute")
async def group_detail(
    request: Request,
    group_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(_get_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> GroupDetail:
    return await get_group_detail(db, current_user.id, group_id)


@router.post("/join", response_model=GroupDetail)
@limiter.limit("20/minute")
async def join(
    request: Request,
    payload: JoinGroupRequest,
    db: Annotated[AsyncSession, Depends(_get_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> GroupDetail:
    return await join_group_by_code(db, current_user, payload.invite_code)


@router.delete(
    "/{group_id}/members/me", status_code=status.HTTP_204_NO_CONTENT
)
@limiter.limit("20/minute")
async def leave(
    request: Request,
    group_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(_get_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> None:
    await leave_group(db, current_user, group_id)


@router.get(
    "/{group_id}/members", response_model=list[GroupMemberResponse]
)
@limiter.limit("60/minute")
async def members(
    request: Request,
    group_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(_get_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[GroupMemberResponse]:
    return await list_group_members(db, current_user.id, group_id)


@router.post(
    "/{group_id}/sessions",
    response_model=GroupSessionResponse,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("10/minute")
async def start(
    request: Request,
    group_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(_get_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> GroupSessionResponse:
    session, candidates = await start_session(db, current_user, group_id)
    schedule_session_timeout(
        session.id,
        lambda: expire_and_broadcast(session.id),
    )
    await broadcast_session_started(
        session.id,
        [c.model_dump(mode="json") for c in candidates],
        session.started_at.isoformat(),
    )
    return await session_to_response(db, session)


@router.get(
    "/{group_id}/sessions/{session_id}",
    response_model=GroupSessionResponse,
)
@limiter.limit("60/minute")
async def session_detail(
    request: Request,
    group_id: uuid.UUID,
    session_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(_get_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> GroupSessionResponse:
    session = await db.get(GroupSession, session_id)
    if session is None or session.group_id != group_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": "Session not found.", "code": "SESSION_NOT_FOUND"},
        )
    await get_group_detail(db, current_user.id, group_id)  # membership check
    return await session_to_response(db, session)


@router.post(
    "/{group_id}/sessions/{session_id}/reroll",
    response_model=GroupSessionResponse,
)
@limiter.limit("5/minute")
async def reroll(
    request: Request,
    group_id: uuid.UUID,
    session_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(_get_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> GroupSessionResponse:
    candidates = await reroll_session_candidates(db, current_user, group_id, session_id)
    await broadcast_session_started(
        session_id,
        [c.model_dump(mode="json") for c in candidates],
        "rerolled",
    )
    session = await db.get(GroupSession, session_id)
    assert session is not None
    return await session_to_response(db, session)


@router.post(
    "/{group_id}/sessions/{session_id}/votes",
    response_model=VoteResponse,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("60/minute")
async def vote(
    request: Request,
    group_id: uuid.UUID,
    session_id: uuid.UUID,
    payload: CastVoteRequest,
    db: Annotated[AsyncSession, Depends(_get_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> VoteResponse:
    session, tally, finished = await cast_vote(
        db, current_user, group_id, session_id, payload.movie_id, payload.vote
    )
    await broadcast_vote_cast(
        session_id, current_user.id, payload.movie_id, payload.vote.value, tally
    )
    if finished and session.recommended_movie_id is not None:
        await broadcast_session_completed(session_id, session.recommended_movie_id)
    return VoteResponse(
        id=uuid.uuid4(),  # actual id is in db; we return a synthetic stable response
        user_id=current_user.id,
        movie_id=payload.movie_id,
        vote=payload.vote,
        voted_at=session.started_at,
    )

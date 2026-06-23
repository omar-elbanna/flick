"""Real-time group session WebSocket endpoint."""

from __future__ import annotations

import asyncio
import uuid
from collections import defaultdict

import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.group import GroupMember, GroupSession, GroupSessionStatus
from app.models.movie import Movie
from app.models.user import User
from app.services.group_service import (
    build_vote_tally,
    expire_session_if_overdue,
    get_session_candidates,
)
from app.utils.jwt_utils import TokenError, verify_access_token

log = structlog.get_logger(__name__)

router = APIRouter()


class WebSocketManager:
    def __init__(self) -> None:
        self._connections: dict[uuid.UUID, list[tuple[WebSocket, uuid.UUID]]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def connect(
        self, session_id: uuid.UUID, user_id: uuid.UUID, ws: WebSocket
    ) -> None:
        async with self._lock:
            self._connections[session_id].append((ws, user_id))

    async def disconnect(self, session_id: uuid.UUID, ws: WebSocket) -> None:
        async with self._lock:
            self._connections[session_id] = [
                c for c in self._connections[session_id] if c[0] is not ws
            ]
            if not self._connections[session_id]:
                self._connections.pop(session_id, None)

    async def broadcast(self, session_id: uuid.UUID, message: dict[str, object]) -> None:
        targets: list[WebSocket]
        async with self._lock:
            targets = [c[0] for c in self._connections.get(session_id, [])]
        for ws in targets:
            try:
                await ws.send_json(message)
            except Exception:
                log.warning("ws.send_failed", session_id=str(session_id))

    async def member_ids(self, session_id: uuid.UUID) -> list[uuid.UUID]:
        async with self._lock:
            return [c[1] for c in self._connections.get(session_id, [])]


manager = WebSocketManager()


async def _authenticate(websocket: WebSocket, token: str | None) -> User | None:
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return None
    try:
        payload = verify_access_token(token)
    except TokenError:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return None
    async with AsyncSessionLocal() as db:
        user = await db.get(User, uuid.UUID(payload["sub"]))
        if user is None or not user.is_active:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return None
        return user


@router.websocket("/sessions/{session_id}")
async def session_socket(
    websocket: WebSocket,
    session_id: uuid.UUID,
    token: str | None = None,
) -> None:
    user = await _authenticate(websocket, token)
    if user is None:
        return

    async with AsyncSessionLocal() as db:
        session = await db.get(GroupSession, session_id)
        if session is None:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
        membership = (
            await db.execute(
                select(GroupMember).where(
                    GroupMember.group_id == session.group_id,
                    GroupMember.user_id == user.id,
                )
            )
        ).scalar_one_or_none()
        if membership is None:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

    await websocket.accept()
    await manager.connect(session_id, user.id, websocket)

    try:
        async with AsyncSessionLocal() as db:
            candidates = await get_session_candidates(session_id)
            tally = await build_vote_tally(db, session_id)
            await websocket.send_json(
                {
                    "type": "session_snapshot",
                    "session_id": str(session_id),
                    "candidates": [c.model_dump(mode="json") for c in candidates],
                    "tally": tally,
                }
            )
        await manager.broadcast(
            session_id,
            {
                "type": "member_joined",
                "user_id": str(user.id),
                "display_name": user.display_name,
            },
        )

        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type") if isinstance(data, dict) else None
            if msg_type == "ping":
                await websocket.send_json({"type": "pong"})
            else:
                # Votes flow through the HTTP endpoint, which then broadcasts.
                pass
    except WebSocketDisconnect:
        pass
    finally:
        await manager.disconnect(session_id, websocket)


async def broadcast_session_started(
    session_id: uuid.UUID, candidates: list[dict[str, object]], started_at: str
) -> None:
    await manager.broadcast(
        session_id,
        {
            "type": "session_started",
            "session_id": str(session_id),
            "candidates": candidates,
            "started_at": started_at,
        },
    )


async def broadcast_vote_cast(
    session_id: uuid.UUID,
    user_id: uuid.UUID,
    movie_id: uuid.UUID,
    vote: str,
    tally: dict[str, dict[str, int]],
) -> None:
    await manager.broadcast(
        session_id,
        {
            "type": "vote_cast",
            "user_id": str(user_id),
            "movie_id": str(movie_id),
            "vote": vote,
            "tally": tally,
        },
    )


async def broadcast_session_completed(
    session_id: uuid.UUID, winner_movie_id: uuid.UUID
) -> None:
    async with AsyncSessionLocal() as db:
        movie = await db.get(Movie, winner_movie_id)
        if movie is None:
            return
        await manager.broadcast(
            session_id,
            {
                "type": "session_completed",
                "session_id": str(session_id),
                "winner_movie_id": str(winner_movie_id),
                "winner_tmdb_id": movie.tmdb_id,
                "winner_title": movie.title,
            },
        )


async def expire_and_broadcast(session_id: uuid.UUID) -> None:
    async with AsyncSessionLocal() as db:
        expired = await expire_session_if_overdue(db, session_id)
        if not expired:
            return
        session = await db.get(GroupSession, session_id)
        if session is None:
            return
        if session.status == GroupSessionStatus.COMPLETED and session.recommended_movie_id:
            await broadcast_session_completed(session_id, session.recommended_movie_id)
        else:
            await manager.broadcast(
                session_id,
                {"type": "session_expired", "session_id": str(session_id)},
            )

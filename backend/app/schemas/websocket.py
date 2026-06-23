"""WebSocket event payload schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.models.group import VoteChoice
from app.schemas.group import SessionCandidate

_BASE = ConfigDict(strict=True)


class WSEvent(BaseModel):
    model_config = _BASE
    type: str


class SessionStartedEvent(BaseModel):
    model_config = _BASE
    type: Literal["session_started"] = "session_started"
    session_id: uuid.UUID
    candidates: list[SessionCandidate]
    started_at: datetime


class MemberJoinedEvent(BaseModel):
    model_config = _BASE
    type: Literal["member_joined"] = "member_joined"
    user_id: uuid.UUID
    display_name: str


class VoteCastEvent(BaseModel):
    model_config = _BASE
    type: Literal["vote_cast"] = "vote_cast"
    user_id: uuid.UUID
    movie_id: uuid.UUID
    vote: VoteChoice
    tally: dict[str, dict[str, int]]


class SessionCompletedEvent(BaseModel):
    model_config = _BASE
    type: Literal["session_completed"] = "session_completed"
    session_id: uuid.UUID
    winner_movie_id: uuid.UUID
    winner_tmdb_id: int
    winner_title: str


class SessionExpiredEvent(BaseModel):
    model_config = _BASE
    type: Literal["session_expired"] = "session_expired"
    session_id: uuid.UUID


class PingMessage(BaseModel):
    model_config = _BASE
    type: Literal["ping"] = "ping"


class PongMessage(BaseModel):
    model_config = _BASE
    type: Literal["pong"] = "pong"

"""Group, member, and session schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.group import GroupMemberRole, GroupSessionStatus, VoteChoice
from app.utils.sanitize import sanitize_required


class CreateGroupRequest(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    name: str = Field(..., min_length=2, max_length=100)

    @field_validator("name")
    @classmethod
    def _sanitize(cls, v: str) -> str:
        return sanitize_required(v, max_length=100)


class JoinGroupRequest(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    invite_code: str = Field(..., min_length=4, max_length=12)


class GroupMemberResponse(BaseModel):
    model_config = ConfigDict(strict=True, from_attributes=True)

    user_id: uuid.UUID
    display_name: str
    avatar_url: str | None = None
    role: GroupMemberRole
    joined_at: datetime


class GroupSummary(BaseModel):
    model_config = ConfigDict(strict=True, from_attributes=True)

    id: uuid.UUID
    name: str
    invite_code: str
    created_at: datetime
    member_count: int
    role: GroupMemberRole


class GroupDetail(BaseModel):
    model_config = ConfigDict(strict=True)

    id: uuid.UUID
    name: str
    invite_code: str
    created_by: uuid.UUID
    created_at: datetime
    is_active: bool
    members: list[GroupMemberResponse]


class SessionCandidate(BaseModel):
    model_config = ConfigDict(strict=True)

    tmdb_id: int
    movie_id: uuid.UUID
    title: str
    poster_path: str | None = None
    overview: str | None = None
    reasoning: str


class GroupSessionResponse(BaseModel):
    model_config = ConfigDict(strict=True)

    id: uuid.UUID
    group_id: uuid.UUID
    status: GroupSessionStatus
    started_by: uuid.UUID
    started_at: datetime
    completed_at: datetime | None = None
    candidates: list[SessionCandidate]
    winner_movie_id: uuid.UUID | None = None
    winner_tmdb_id: int | None = None


class CastVoteRequest(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    movie_id: uuid.UUID
    vote: VoteChoice


class VoteResponse(BaseModel):
    model_config = ConfigDict(strict=True, from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    movie_id: uuid.UUID
    vote: VoteChoice
    voted_at: datetime

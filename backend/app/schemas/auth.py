"""Authentication request and response schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.utils.sanitize import sanitize_required

_STRICT = ConfigDict(strict=True, extra="forbid")
_RESPONSE = ConfigDict(strict=True, from_attributes=True)


class RegisterRequest(BaseModel):
    model_config = _STRICT

    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    display_name: str = Field(..., min_length=2, max_length=50)

    @field_validator("display_name")
    @classmethod
    def _sanitize_display_name(cls, v: str) -> str:
        return sanitize_required(v, max_length=50)


class LoginRequest(BaseModel):
    model_config = _STRICT

    email: EmailStr
    password: str = Field(..., min_length=1, max_length=128)


class TokenResponse(BaseModel):
    model_config = _STRICT

    access_token: str
    token_type: str = "bearer"
    expires_in: int


class UserResponse(BaseModel):
    model_config = _RESPONSE

    id: uuid.UUID
    email: EmailStr
    display_name: str
    avatar_url: str | None = None
    created_at: datetime


class GoogleCallbackResponse(BaseModel):
    model_config = _STRICT

    user: UserResponse
    access_token: str
    expires_in: int

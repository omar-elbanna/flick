"""JWT (RS256) creation, verification, and refresh token rotation."""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, TypedDict

import structlog
from jose import JWTError, jwt
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.user import RefreshToken, User

log = structlog.get_logger(__name__)

ALGORITHM = "RS256"


class AccessTokenPayload(TypedDict):
    sub: str
    email: str
    iat: int
    exp: int
    iss: str
    aud: str
    type: str


class RefreshTokenIssued(TypedDict):
    raw_token: str
    token_hash: str
    family_id: uuid.UUID
    expires_at: datetime


class TokenError(Exception):
    """Generic token verification error."""


class TokenReuseError(Exception):
    """Raised when a revoked refresh token is presented (token theft)."""


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def create_access_token(user_id: uuid.UUID, email: str) -> str:
    now = _now()
    exp = now + timedelta(minutes=settings.ACCESS_TOKEN_TTL_MINUTES)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "email": email,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
        "type": "access",
    }
    return jwt.encode(payload, settings.RSA_PRIVATE_KEY, algorithm=ALGORITHM)


def verify_access_token(token: str) -> AccessTokenPayload:
    try:
        decoded = jwt.decode(
            token,
            settings.RSA_PUBLIC_KEY,
            algorithms=[ALGORITHM],
            audience=settings.JWT_AUDIENCE,
            issuer=settings.JWT_ISSUER,
        )
    except JWTError as exc:
        raise TokenError(str(exc)) from exc
    if decoded.get("type") != "access":
        raise TokenError("wrong token type")
    return AccessTokenPayload(**decoded)


def create_refresh_token(user_id: uuid.UUID, family_id: uuid.UUID) -> RefreshTokenIssued:
    """Generate a random opaque refresh token + its DB-bound metadata.

    The raw token is returned exactly once (to the client). Only the SHA-256
    hash is stored in the database.
    """

    raw_token = secrets.token_urlsafe(48)
    expires_at = _now() + timedelta(days=settings.REFRESH_TOKEN_TTL_DAYS)
    return RefreshTokenIssued(
        raw_token=raw_token,
        token_hash=_hash_token(raw_token),
        family_id=family_id,
        expires_at=expires_at,
    )


async def persist_refresh_token(
    db: AsyncSession,
    user_id: uuid.UUID,
    issued: RefreshTokenIssued,
    *,
    ip_address: str | None,
    user_agent: str | None,
) -> RefreshToken:
    token = RefreshToken(
        user_id=user_id,
        token_hash=issued["token_hash"],
        family_id=issued["family_id"],
        expires_at=issued["expires_at"],
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db.add(token)
    await db.flush()
    return token


async def _revoke_family(db: AsyncSession, family_id: uuid.UUID) -> None:
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=_now())
    )


async def verify_and_rotate_refresh_token(
    raw_token: str,
    db: AsyncSession,
    *,
    ip_address: str | None,
    user_agent: str | None,
) -> tuple[str, User]:
    """Verify a refresh token, rotate it, and return (new_raw_token, user).

    Token theft detection: if a token that has already been revoked is reused,
    we revoke the entire family and raise TokenReuseError.
    """

    token_hash = _hash_token(raw_token)
    stmt = select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    record = (await db.execute(stmt)).scalar_one_or_none()
    if record is None:
        raise TokenError("refresh token not recognized")

    if record.revoked_at is not None:
        # Reuse of a revoked token — assume the family has been compromised.
        await _revoke_family(db, record.family_id)
        await db.commit()
        log.warning("auth.token_theft_detected", family_id=str(record.family_id))
        raise TokenReuseError("refresh token reuse detected; family revoked")

    if record.expires_at <= _now():
        raise TokenError("refresh token expired")

    user = await db.get(User, record.user_id)
    if user is None or not user.is_active:
        raise TokenError("user not found or inactive")

    # Rotate: revoke this token, issue a new one in the same family.
    record.revoked_at = _now()
    issued = create_refresh_token(user.id, record.family_id)
    await persist_refresh_token(
        db, user.id, issued, ip_address=ip_address, user_agent=user_agent
    )
    await db.commit()
    return issued["raw_token"], user


async def revoke_refresh_token_family_by_raw(
    raw_token: str,
    db: AsyncSession,
) -> bool:
    token_hash = _hash_token(raw_token)
    record = (
        await db.execute(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    ).scalar_one_or_none()
    if record is None:
        return False
    await _revoke_family(db, record.family_id)
    await db.commit()
    return True


def new_token_family_id() -> uuid.UUID:
    return uuid.uuid4()

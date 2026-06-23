"""Authentication service — registration, login, OAuth, logout."""

from __future__ import annotations

import secrets
import uuid
from typing import Any

import httpx
import structlog
from fastapi import HTTPException, status
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.taste_profile import UserTasteProfile
from app.models.user import User
from app.schemas.auth import RegisterRequest
from app.utils.jwt_utils import (
    create_access_token,
    create_refresh_token,
    new_token_family_id,
    persist_refresh_token,
)

log = structlog.get_logger(__name__)

pwd_context = CryptContext(schemes=["bcrypt"], bcrypt__rounds=12, deprecated="auto")

GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"  # noqa: S105 — public URL
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


async def register_user(db: AsyncSession, payload: RegisterRequest) -> User:
    existing = (
        await db.execute(select(User).where(User.email == payload.email))
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"detail": "Email already registered.", "code": "EMAIL_TAKEN"},
        )
    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        display_name=payload.display_name,
    )
    db.add(user)
    await db.flush()
    db.add(UserTasteProfile(user_id=user.id))
    await db.commit()
    await db.refresh(user)
    return user


async def authenticate_user(db: AsyncSession, email: str, password: str) -> User:
    user = (
        await db.execute(select(User).where(User.email == email))
    ).scalar_one_or_none()
    if user is None or user.hashed_password is None:
        log.info("auth.login_failed", reason="no_password_user")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"detail": "Invalid credentials.", "code": "INVALID_CREDENTIALS"},
        )
    if not verify_password(password, user.hashed_password):
        log.info("auth.login_failed", reason="bad_password", user_id=str(user.id))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"detail": "Invalid credentials.", "code": "INVALID_CREDENTIALS"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"detail": "Account disabled.", "code": "ACCOUNT_DISABLED"},
        )
    return user


async def issue_token_pair(
    db: AsyncSession,
    user: User,
    *,
    ip_address: str | None,
    user_agent: str | None,
) -> tuple[str, str]:
    """Return (access_token, raw_refresh_token) for a fresh login or OAuth grant."""

    access_token = create_access_token(user.id, user.email)
    issued = create_refresh_token(user.id, new_token_family_id())
    await persist_refresh_token(
        db, user.id, issued, ip_address=ip_address, user_agent=user_agent
    )
    await db.commit()
    return access_token, issued["raw_token"]


def build_google_auth_url(state: str, code_challenge: str) -> str:
    from urllib.parse import urlencode

    params = {
        "response_type": "code",
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "scope": "openid email profile",
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "access_type": "online",
        "prompt": "select_account",
    }
    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"


async def exchange_google_code(code: str, code_verifier: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "redirect_uri": settings.GOOGLE_REDIRECT_URI,
                "grant_type": "authorization_code",
                "code_verifier": code_verifier,
            },
        )
    if resp.status_code != 200:
        log.warning("auth.oauth_token_exchange_failed", status_code=resp.status_code)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": "OAuth exchange failed.", "code": "OAUTH_EXCHANGE_FAILED"},
        )
    return resp.json()


async def fetch_google_userinfo(access_token: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
    if resp.status_code != 200:
        log.warning("auth.oauth_userinfo_failed", status_code=resp.status_code)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": "Failed to fetch Google profile.", "code": "OAUTH_USERINFO_FAILED"},
        )
    return resp.json()


async def handle_google_callback(
    db: AsyncSession,
    *,
    code: str,
    code_verifier: str,
) -> User:
    token_data = await exchange_google_code(code, code_verifier)
    access_token = token_data.get("access_token")
    if not isinstance(access_token, str):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": "OAuth response missing access token.", "code": "OAUTH_INVALID"},
        )
    profile = await fetch_google_userinfo(access_token)
    google_id = profile.get("sub")
    email = profile.get("email")
    name = profile.get("name") or (email.split("@")[0] if isinstance(email, str) else "User")
    avatar = profile.get("picture")
    if not google_id or not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": "Google profile incomplete.", "code": "OAUTH_INCOMPLETE_PROFILE"},
        )

    user = (
        await db.execute(select(User).where(User.google_id == google_id))
    ).scalar_one_or_none()
    if user is None:
        user = (
            await db.execute(select(User).where(User.email == email))
        ).scalar_one_or_none()
        if user is None:
            user = User(
                email=email,
                hashed_password=None,
                display_name=name[:50],
                google_id=google_id,
                avatar_url=avatar,
            )
            db.add(user)
            await db.flush()
            db.add(UserTasteProfile(user_id=user.id))
        else:
            user.google_id = google_id
            if avatar and not user.avatar_url:
                user.avatar_url = avatar
        await db.commit()
        await db.refresh(user)
    return user


def generate_pkce_pair() -> tuple[str, str]:
    """Return (code_verifier, code_challenge) per RFC 7636 with S256."""

    import base64
    import hashlib

    verifier = secrets.token_urlsafe(64)[:96]
    challenge_bytes = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(challenge_bytes).rstrip(b"=").decode("ascii")
    return verifier, challenge


def generate_oauth_state() -> str:
    return secrets.token_urlsafe(32)


def _normalize_uuid(value: str | uuid.UUID) -> uuid.UUID:
    return value if isinstance(value, uuid.UUID) else uuid.UUID(value)

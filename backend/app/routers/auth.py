"""Authentication router — register, login, refresh, logout, Google OAuth, me."""

from __future__ import annotations

import json
from typing import Annotated

import structlog
from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.dependencies import (
    _get_session,
    get_client_ip,
    get_current_user,
    get_user_agent,
)
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from app.services.auth_service import (
    authenticate_user,
    build_google_auth_url,
    generate_oauth_state,
    generate_pkce_pair,
    handle_google_callback,
    issue_token_pair,
    register_user,
)
from app.utils.jwt_utils import (
    TokenError,
    TokenReuseError,
    create_access_token,
    revoke_refresh_token_family_by_raw,
    verify_and_rotate_refresh_token,
)
from app.utils.rate_limit import limiter

log = structlog.get_logger(__name__)

router = APIRouter()

REFRESH_COOKIE_NAME = "flick_refresh"
OAUTH_STATE_COOKIE = "flick_oauth_state"
OAUTH_VERIFIER_COOKIE = "flick_oauth_verifier"  # noqa: S105 — cookie name only


def _set_refresh_cookie(response: Response, raw_token: str) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=raw_token,
        max_age=settings.REFRESH_TOKEN_TTL_DAYS * 24 * 60 * 60,
        httponly=True,
        secure=settings.is_production,
        samesite="strict",
        path="/api/v1/auth",
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(REFRESH_COOKIE_NAME, path="/api/v1/auth")


def _token_response(access_token: str) -> TokenResponse:
    return TokenResponse(
        access_token=access_token,
        expires_in=settings.ACCESS_TOKEN_TTL_MINUTES * 60,
    )


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
async def register(
    request: Request,
    payload: RegisterRequest,
    db: Annotated[AsyncSession, Depends(_get_session)],
) -> UserResponse:
    user = await register_user(db, payload)
    log.info("auth.user_registered", user_id=str(user.id))
    return UserResponse.model_validate(user)


@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/minute")
async def login(
    request: Request,
    response: Response,
    payload: LoginRequest,
    db: Annotated[AsyncSession, Depends(_get_session)],
) -> TokenResponse:
    user = await authenticate_user(db, payload.email, payload.password)
    access_token, raw_refresh = await issue_token_pair(
        db, user, ip_address=get_client_ip(request), user_agent=get_user_agent(request)
    )
    _set_refresh_cookie(response, raw_refresh)
    log.info("auth.login_success", user_id=str(user.id))
    return _token_response(access_token)


@router.post("/refresh", response_model=TokenResponse)
@limiter.limit("30/minute")
async def refresh(
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(_get_session)],
    refresh_cookie: Annotated[str | None, Cookie(alias=REFRESH_COOKIE_NAME)] = None,
) -> TokenResponse:
    if not refresh_cookie:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"detail": "Refresh token missing.", "code": "REFRESH_MISSING"},
        )
    try:
        new_raw, user = await verify_and_rotate_refresh_token(
            refresh_cookie,
            db,
            ip_address=get_client_ip(request),
            user_agent=get_user_agent(request),
        )
    except TokenReuseError:
        _clear_refresh_cookie(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "detail": "Token reuse detected. Please log in again.",
                "code": "TOKEN_REUSE",
            },
        ) from None
    except TokenError:
        _clear_refresh_cookie(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"detail": "Invalid refresh token.", "code": "REFRESH_INVALID"},
        ) from None

    access_token = create_access_token(user.id, user.email)
    _set_refresh_cookie(response, new_raw)
    return _token_response(access_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(_get_session)],
    refresh_cookie: Annotated[str | None, Cookie(alias=REFRESH_COOKIE_NAME)] = None,
) -> Response:
    if refresh_cookie:
        await revoke_refresh_token_family_by_raw(refresh_cookie, db)
    _clear_refresh_cookie(response)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/google", status_code=status.HTTP_307_TEMPORARY_REDIRECT)
@limiter.limit("10/minute")
async def google_login(request: Request) -> RedirectResponse:
    verifier, challenge = generate_pkce_pair()
    state = generate_oauth_state()
    url = build_google_auth_url(state, challenge)
    resp = RedirectResponse(url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)
    cookie_kwargs = {
        "httponly": True,
        "secure": settings.is_production,
        "samesite": "lax",
        "max_age": 600,
        "path": "/api/v1/auth",
    }
    resp.set_cookie(OAUTH_STATE_COOKIE, state, **cookie_kwargs)
    resp.set_cookie(OAUTH_VERIFIER_COOKIE, verifier, **cookie_kwargs)
    return resp


@router.get("/google/callback")
@limiter.limit("10/minute")
async def google_callback(
    request: Request,
    db: Annotated[AsyncSession, Depends(_get_session)],
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    state_cookie: Annotated[str | None, Cookie(alias=OAUTH_STATE_COOKIE)] = None,
    verifier_cookie: Annotated[str | None, Cookie(alias=OAUTH_VERIFIER_COOKIE)] = None,
) -> RedirectResponse:
    if error:
        log.warning("auth.oauth_provider_error", error=error)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": "OAuth provider returned an error.", "code": "OAUTH_PROVIDER_ERROR"},
        )
    if not code or not state or not state_cookie or not verifier_cookie:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": "OAuth state or code missing.", "code": "OAUTH_STATE_MISSING"},
        )
    if state != state_cookie:
        log.warning("auth.oauth_state_mismatch")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": "OAuth state mismatch.", "code": "OAUTH_STATE_MISMATCH"},
        )

    user = await handle_google_callback(db, code=code, code_verifier=verifier_cookie)
    access_token, raw_refresh = await issue_token_pair(
        db, user, ip_address=get_client_ip(request), user_agent=get_user_agent(request)
    )

    redirect_url = (
        f"{settings.FRONTEND_URL}/auth/callback?access_token={access_token}"
        f"&expires_in={settings.ACCESS_TOKEN_TTL_MINUTES * 60}"
    )
    resp = RedirectResponse(redirect_url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)
    _set_refresh_cookie(resp, raw_refresh)
    resp.delete_cookie(OAUTH_STATE_COOKIE, path="/api/v1/auth")
    resp.delete_cookie(OAUTH_VERIFIER_COOKIE, path="/api/v1/auth")
    log.info("auth.oauth_login_success", user_id=str(user.id))
    return resp


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: Annotated[User, Depends(get_current_user)]) -> UserResponse:
    return UserResponse.model_validate(current_user)


# Re-export to satisfy unused-import linters when json is not otherwise used.
_ = json

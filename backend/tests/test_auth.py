"""Authentication: register, login, refresh, logout, token theft detection."""

from __future__ import annotations

from httpx import AsyncClient


async def test_register_and_login(client: AsyncClient, user_payload: dict[str, str]) -> None:
    r = await client.post("/api/v1/auth/register", json=user_payload)
    assert r.status_code == 201
    body = r.json()
    assert body["email"] == user_payload["email"]

    login = await client.post(
        "/api/v1/auth/login",
        json={"email": user_payload["email"], "password": user_payload["password"]},
    )
    assert login.status_code == 200
    assert "access_token" in login.json()
    assert "flick_refresh" in login.cookies


async def test_register_duplicate_email_conflicts(
    client: AsyncClient, user_payload: dict[str, str]
) -> None:
    r1 = await client.post("/api/v1/auth/register", json=user_payload)
    assert r1.status_code == 201
    r2 = await client.post("/api/v1/auth/register", json=user_payload)
    assert r2.status_code == 409


async def test_login_bad_password_rejected(
    client: AsyncClient, user_payload: dict[str, str]
) -> None:
    await client.post("/api/v1/auth/register", json=user_payload)
    bad = await client.post(
        "/api/v1/auth/login",
        json={"email": user_payload["email"], "password": "wrongpassword!"},
    )
    assert bad.status_code == 401


async def test_me_requires_auth(client: AsyncClient) -> None:
    r = await client.get("/api/v1/auth/me")
    assert r.status_code == 401


async def test_me_with_token(client: AsyncClient, auth_token: str) -> None:
    r = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert r.status_code == 200


async def test_refresh_rotates_cookie(
    client: AsyncClient, user_payload: dict[str, str]
) -> None:
    await client.post("/api/v1/auth/register", json=user_payload)
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": user_payload["email"], "password": user_payload["password"]},
    )
    original_cookie = login.cookies.get("flick_refresh")
    assert original_cookie

    refresh = await client.post(
        "/api/v1/auth/refresh", cookies={"flick_refresh": original_cookie}
    )
    assert refresh.status_code == 200
    new_cookie = refresh.cookies.get("flick_refresh")
    assert new_cookie and new_cookie != original_cookie


async def test_token_theft_revokes_family(
    client: AsyncClient, user_payload: dict[str, str]
) -> None:
    await client.post("/api/v1/auth/register", json=user_payload)
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": user_payload["email"], "password": user_payload["password"]},
    )
    original_cookie = login.cookies.get("flick_refresh")
    assert original_cookie

    # First refresh — succeeds, original is revoked.
    r1 = await client.post(
        "/api/v1/auth/refresh", cookies={"flick_refresh": original_cookie}
    )
    assert r1.status_code == 200

    # Reuse of the now-revoked token — should fail with token reuse code.
    r2 = await client.post(
        "/api/v1/auth/refresh", cookies={"flick_refresh": original_cookie}
    )
    assert r2.status_code == 401
    assert r2.json()["detail"]["code"] == "TOKEN_REUSE"

    # Even the freshly-rotated token from r1 is now part of a revoked family.
    rotated = r1.cookies.get("flick_refresh")
    assert rotated
    r3 = await client.post(
        "/api/v1/auth/refresh", cookies={"flick_refresh": rotated}
    )
    assert r3.status_code == 401


async def test_logout_invalidates_refresh(
    client: AsyncClient, user_payload: dict[str, str]
) -> None:
    await client.post("/api/v1/auth/register", json=user_payload)
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": user_payload["email"], "password": user_payload["password"]},
    )
    cookie = login.cookies.get("flick_refresh")
    assert cookie

    logout = await client.post(
        "/api/v1/auth/logout", cookies={"flick_refresh": cookie}
    )
    assert logout.status_code == 204

    after = await client.post("/api/v1/auth/refresh", cookies={"flick_refresh": cookie})
    assert after.status_code == 401

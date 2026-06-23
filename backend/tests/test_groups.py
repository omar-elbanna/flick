"""Group CRUD: create, list, invite, join, 404 on bad code."""

from __future__ import annotations

from httpx import AsyncClient


async def test_create_group(client: AsyncClient, auth_token: str) -> None:
    headers = {"Authorization": f"Bearer {auth_token}"}
    r = await client.post(
        "/api/v1/groups", headers=headers, json={"name": "Movie buddies"}
    )
    assert r.status_code == 201
    body = r.json()
    assert body["name"] == "Movie buddies"
    assert body["role"] == "owner"
    assert len(body["invite_code"]) == 8


async def test_list_groups(client: AsyncClient, auth_token: str) -> None:
    headers = {"Authorization": f"Bearer {auth_token}"}
    await client.post(
        "/api/v1/groups", headers=headers, json={"name": "Alpha"}
    )
    await client.post(
        "/api/v1/groups", headers=headers, json={"name": "Beta"}
    )
    r = await client.get("/api/v1/groups", headers=headers)
    assert r.status_code == 200
    assert len(r.json()) >= 2


async def test_join_invalid_code_returns_404(
    client: AsyncClient, auth_token: str
) -> None:
    headers = {"Authorization": f"Bearer {auth_token}"}
    r = await client.post(
        "/api/v1/groups/join", headers=headers, json={"invite_code": "ZZZZZZZZ"}
    )
    assert r.status_code == 404
    assert r.json()["detail"]["code"] == "INVITE_NOT_FOUND"


async def test_join_by_code(client: AsyncClient, auth_token: str) -> None:
    headers = {"Authorization": f"Bearer {auth_token}"}
    created = await client.post(
        "/api/v1/groups", headers=headers, json={"name": "Joinable"}
    )
    code = created.json()["invite_code"]
    # Joining again as the owner is a no-op but returns detail.
    r = await client.post(
        "/api/v1/groups/join", headers=headers, json={"invite_code": code}
    )
    assert r.status_code == 200
    assert r.json()["name"] == "Joinable"

"""Rating endpoints — create, update, delete, paginate."""

from __future__ import annotations

from httpx import AsyncClient


async def test_create_rating(client: AsyncClient, auth_token: str) -> None:
    r = await client.post(
        "/api/v1/ratings",
        headers={"Authorization": f"Bearer {auth_token}"},
        json={"tmdb_id": 42, "score": 5, "review": "Loved it"},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["score"] == 5
    assert body["review"] == "Loved it"


async def test_update_rating_via_upsert(
    client: AsyncClient, auth_token: str
) -> None:
    headers = {"Authorization": f"Bearer {auth_token}"}
    await client.post(
        "/api/v1/ratings", headers=headers, json={"tmdb_id": 42, "score": 3}
    )
    r = await client.post(
        "/api/v1/ratings", headers=headers, json={"tmdb_id": 42, "score": 5}
    )
    assert r.status_code == 201
    assert r.json()["score"] == 5


async def test_delete_rating(client: AsyncClient, auth_token: str) -> None:
    headers = {"Authorization": f"Bearer {auth_token}"}
    created = await client.post(
        "/api/v1/ratings", headers=headers, json={"tmdb_id": 99, "score": 4}
    )
    rid = created.json()["id"]
    r = await client.delete(f"/api/v1/ratings/{rid}", headers=headers)
    assert r.status_code == 204


async def test_list_my_ratings_paginates(
    client: AsyncClient, auth_token: str
) -> None:
    headers = {"Authorization": f"Bearer {auth_token}"}
    for tmdb in [1, 2, 3]:
        await client.post(
            "/api/v1/ratings", headers=headers, json={"tmdb_id": tmdb, "score": 4}
        )
    r = await client.get("/api/v1/users/me/ratings", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 3
    assert len(body["items"]) == 3

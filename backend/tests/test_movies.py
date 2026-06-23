"""Movie endpoints with TMDB client mocked."""

from __future__ import annotations

from httpx import AsyncClient


async def test_search_requires_auth(client: AsyncClient) -> None:
    r = await client.get("/api/v1/movies/search", params={"q": "matrix"})
    assert r.status_code == 401


async def test_search_returns_mocked_results(
    client: AsyncClient, auth_token: str
) -> None:
    r = await client.get(
        "/api/v1/movies/search",
        params={"q": "matrix"},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["page"] == 1


async def test_movie_detail_upserts_to_db(
    client: AsyncClient, auth_token: str
) -> None:
    r = await client.get(
        "/api/v1/movies/603",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["tmdb_id"] == 603
    assert body["title"] == "Movie 603"

"""Pytest fixtures — isolated SQLite DB, mocked external services."""

from __future__ import annotations

import asyncio
import os
import uuid
from collections.abc import AsyncGenerator, Generator
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio

# Force test environment BEFORE importing app modules so the Settings refuses
# to validate against the developer's real .env.
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "memory://")
os.environ.setdefault(
    "RSA_PRIVATE_KEY",
    "",
)
os.environ.setdefault("RSA_PUBLIC_KEY", "")
os.environ.setdefault("GOOGLE_CLIENT_ID", "test-client-id")
os.environ.setdefault("GOOGLE_CLIENT_SECRET", "test-client-secret")
os.environ.setdefault("TMDB_API_KEY", "test-tmdb-key")
os.environ.setdefault("OPENAI_API_KEY", "test-openai-key")
os.environ.setdefault("FRONTEND_URL", "http://localhost:3000")
os.environ.setdefault("ALLOWED_ORIGINS", "http://localhost:3000")
os.environ.setdefault("SESSION_SECRET", "test-session-secret-please-rotate")

# Generate a test RSA key pair once and inject.
if not os.environ.get("RSA_PRIVATE_KEY"):
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    priv = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    pub = (
        key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode()
    )
    os.environ["RSA_PRIVATE_KEY"] = priv
    os.environ["RSA_PUBLIC_KEY"] = pub

from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy.ext.asyncio import (  # noqa: E402
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

import app.database as db_module  # noqa: E402
from app import models as _models  # noqa: E402, F401 — registers tables on Base.metadata
from app.database import Base  # noqa: E402


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def db_engine() -> AsyncGenerator[Any, None]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine: Any) -> AsyncGenerator[AsyncSession, None]:
    sessionmaker = async_sessionmaker(db_engine, expire_on_commit=False)
    async with sessionmaker() as s:
        yield s


@pytest_asyncio.fixture
async def client(
    db_engine: Any, monkeypatch: pytest.MonkeyPatch
) -> AsyncGenerator[AsyncClient, None]:
    # Point the app's engine and session factory at the in-memory test DB.
    test_sessionmaker = async_sessionmaker(db_engine, expire_on_commit=False)
    monkeypatch.setattr(db_module, "engine", db_engine, raising=True)
    monkeypatch.setattr(db_module, "AsyncSessionLocal", test_sessionmaker, raising=True)

    # Patch out external services so tests don't hit the network. Patch the
    # imported-into-module reference (where it's USED) not the source, otherwise
    # the route handlers still see the real function.
    with (
        patch("app.services.movie_service.get_movie_detail", new_callable=AsyncMock) as tmdb_detail,
        patch("app.routers.movies.search_movies", new_callable=AsyncMock) as tmdb_search,
        patch("app.routers.movies.get_trending", new_callable=AsyncMock) as tmdb_trending,
        patch("app.routers.movies.get_genres", new_callable=AsyncMock) as tmdb_genres,
        patch("app.services.recommendation_service.call_with_retry", new_callable=AsyncMock) as openai_call,
        patch("app.services.recommendation_service.search_movies", new_callable=AsyncMock) as reco_search,
        patch("app.utils.redis_client.get_redis", new_callable=AsyncMock) as redis_mock,
        patch("app.utils.redis_client.cache_get", new_callable=AsyncMock, return_value=None),
        patch("app.utils.redis_client.cache_set", new_callable=AsyncMock, return_value=None),
        patch("app.utils.redis_client.cache_delete", new_callable=AsyncMock, return_value=None),
    ):
        redis_mock.return_value = AsyncMock()
        tmdb_search.return_value = {
            "page": 1,
            "results": [],
            "total_pages": 0,
            "total_results": 0,
        }
        tmdb_trending.return_value = {
            "page": 1,
            "results": [],
            "total_pages": 0,
            "total_results": 0,
        }
        tmdb_genres.return_value = {"genres": [{"id": 28, "name": "Action"}]}

        def make_tmdb(tmdb_id: int) -> dict[str, Any]:
            return {
                "id": tmdb_id,
                "title": f"Movie {tmdb_id}",
                "overview": "Test overview",
                "release_date": "2024-01-01",
                "poster_path": None,
                "backdrop_path": None,
                "genres": [{"id": 28, "name": "Action"}],
                "runtime": 100,
                "vote_average": 7.5,
                "vote_count": 100,
                "original_language": "en",
            }

        tmdb_detail.side_effect = lambda tmdb_id: make_tmdb(int(tmdb_id))
        reco_search.return_value = {
            "page": 1,
            "results": [],
            "total_pages": 0,
            "total_results": 0,
        }

        openai_call.return_value = {
            "recommendations": [
                {"title": f"Reco {i}", "year": 2020 + i, "reasoning": "test"}
                for i in range(5)
            ]
        }

        from app.main import app

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://test", follow_redirects=False
        ) as ac:
            yield ac


@pytest.fixture
def user_payload() -> dict[str, str]:
    return {
        "email": f"u{uuid.uuid4().hex[:8]}@example.com",
        "password": "supersecret123",
        "display_name": "Test User",
    }


@pytest_asyncio.fixture
async def auth_token(client: AsyncClient, user_payload: dict[str, str]) -> str:
    resp = await client.post("/api/v1/auth/register", json=user_payload)
    assert resp.status_code == 201
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": user_payload["email"], "password": user_payload["password"]},
    )
    assert login.status_code == 200
    return str(login.json()["access_token"])

"""FastAPI application entry point."""

from __future__ import annotations

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.config import settings
from app.middleware.https_redirect import HTTPSRedirectMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.routers import (
    auth as auth_router,
    groups as groups_router,
    movies as movies_router,
    ratings as ratings_router,
    recommendations as recommendations_router,
    watchlist as watchlist_router,
    websocket as websocket_router,
)
from app.utils.logging import configure_logging
from app.utils.rate_limit import limiter
from app.utils.redis_client import close_redis, get_redis

log = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    log.info("flick.startup", environment=settings.ENVIRONMENT)
    await get_redis()
    yield
    await close_redis()
    log.info("flick.shutdown")


app = FastAPI(
    title="Flick API",
    description="Group movie recommendations with real-time sessions.",
    version="0.1.0",
    docs_url="/docs" if not settings.is_production else None,
    redoc_url="/redoc" if not settings.is_production else None,
    openapi_url="/openapi.json" if not settings.is_production else None,
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

if settings.is_production:
    app.add_middleware(HTTPSRedirectMiddleware)

app.add_middleware(SecurityHeadersMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
    expose_headers=["Retry-After"],
    max_age=600,
)

app.include_router(auth_router.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(movies_router.router, prefix="/api/v1/movies", tags=["movies"])
app.include_router(ratings_router.router, prefix="/api/v1", tags=["ratings"])
app.include_router(watchlist_router.router, prefix="/api/v1", tags=["watchlist"])
app.include_router(
    recommendations_router.router, prefix="/api/v1/recommendations", tags=["recommendations"]
)
app.include_router(groups_router.router, prefix="/api/v1/groups", tags=["groups"])
app.include_router(websocket_router.router, prefix="/api/v1/ws", tags=["websocket"])


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    return {"status": "ok", "environment": settings.ENVIRONMENT}


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    log.error(
        "flick.unhandled_exception",
        path=request.url.path,
        method=request.method,
        error_type=type(exc).__name__,
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "code": "INTERNAL_ERROR"},
    )

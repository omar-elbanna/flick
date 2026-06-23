"""Redirect plain HTTP to HTTPS in production deployments.

Honors X-Forwarded-Proto so it works behind common reverse proxies.
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response


class HTTPSRedirectMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        forwarded_proto = request.headers.get("x-forwarded-proto", "").lower()
        proto = forwarded_proto or request.url.scheme
        if proto == "https" or request.url.path.startswith("/health"):
            return await call_next(request)
        target = request.url.replace(scheme="https")
        return RedirectResponse(str(target), status_code=308)

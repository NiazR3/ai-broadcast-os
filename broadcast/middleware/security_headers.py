"""Middleware that injects security-related HTTP headers on every response.

This middleware sets:

- ``X-Content-Type-Options: nosniff`` -- prevents MIME-type sniffing.
- ``X-Frame-Options: DENY`` -- prevents clickjacking by disallowing framing.
- ``Content-Security-Policy`` -- restricts resource loading to same-origin,
  permits WebSocket connections to the broadcast port, and allows inline
  styles (for frontend tooling).
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add hardened security headers to every HTTP response."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "connect-src 'self' ws://localhost:8100; "
            "style-src 'self' 'unsafe-inline';"
        )
        return response

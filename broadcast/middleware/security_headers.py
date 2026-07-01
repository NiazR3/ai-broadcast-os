"""Middleware that injects security-related HTTP headers on every response.

This middleware sets:

- ``X-Content-Type-Options: nosniff`` -- prevents MIME-type sniffing.
- ``X-Frame-Options: DENY`` -- prevents clickjacking by disallowing framing.
- ``Permissions-Policy`` -- disables all unused browser APIs (geolocation,
  camera, microphone, accelerometer, etc.) to reduce the attack surface.
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
        response.headers["Permissions-Policy"] = (
            "geolocation=(), camera=(), microphone=(), accelerometer=(), "
            "autoplay=(), clipboard-read=(), clipboard-write=(), display-capture=(), "
            "encrypted-media=(), fullscreen=(), gamepad=(), gyroscope=(), "
            "magnetometer=(), midi=(), payment=(), picture-in-picture=(), "
            "publickey-credentials-get=(), screen-wake-lock=(), sync-xhr=(), "
            "usb=(), web-share=(), xr-spatial-tracking=()"
        )
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "connect-src 'self' ws://localhost:8100; "
            "style-src 'self' 'unsafe-inline';"
        )
        return response

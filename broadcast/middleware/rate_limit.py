"""Simple in-memory rate limiter using a sliding window per IP address.

Provides a single RateLimitMiddleware class that can be added to a FastAPI
application via ``app.add_middleware()``.  Stricter limits are applied to
POST endpoints (state-changing operations) than to read-only GET requests.
"""

from __future__ import annotations

import time
from collections import defaultdict

from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limit by IP address using a sliding window.

    Attributes:
        default_limit: Maximum number of requests per ``window_seconds`` for GET (and other non-POST) methods.
        post_limit: Stricter limit for POST requests (state-changing operations).
        window_seconds: Width of the sliding window in seconds.
    """

    def __init__(
        self,
        app,
        default_limit: int = 60,
        post_limit: int = 10,
        window_seconds: int = 60,
    ) -> None:
        super().__init__(app)
        self.default_limit = default_limit
        self.post_limit = post_limit
        self.window_seconds = window_seconds
        self._requests: dict[str, list[float]] = defaultdict(list)

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # Only rate-limit broadcast routes
        if not request.url.path.startswith("/broadcast"):
            return await call_next(request)

        # Determine limit based on HTTP method
        limit = self.post_limit if request.method == "POST" else self.default_limit

        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        window_start = now - self.window_seconds

        # Purge entries outside the current window
        timestamps = self._requests[client_ip]
        self._requests[client_ip] = [t for t in timestamps if t > window_start]

        if len(self._requests[client_ip]) >= limit:
            raise HTTPException(status_code=429, detail="Too many requests")

        self._requests[client_ip].append(now)
        return await call_next(request)

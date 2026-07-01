"""Simple in-memory rate limiter using a sliding window per IP address.

Provides a single RateLimitMiddleware class that can be added to a FastAPI
application via ``app.add_middleware()``.  Stricter limits are applied to
POST endpoints (state-changing operations) than to read-only GET requests.
"""

from __future__ import annotations

import time
from collections import defaultdict

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse, Response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limit by IP address using a sliding window.

    WARNING: This rate limiter stores state in-process memory only.
    It MUST NOT be used with uvicorn ``--workers N`` or any multi-process
    deployment (gunicorn, etc.) without a shared backend (e.g. Redis).
    Each worker process has its own independent state, making the effective
    rate limit ``N * configured_limit`` per process.
    The current Dockerfile CMD uses 1 worker; adding ``--workers`` without
    switching to a shared-state backend will silently degrade rate limiting.

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
        # WARNING: in-process only -- NOT shared across uvicorn workers.
        # Adding --workers N creates N independent rate-limit states,
        # making the effective limit N * configured_limit per IP.
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

        remaining = max(0, limit - len(self._requests[client_ip]))
        window_end = int(now - (now % self.window_seconds) + self.window_seconds)

        if remaining == 0:
            retry_after = int(window_end - now) + 1
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests"},
                headers={
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(window_end),
                    "Retry-After": str(retry_after),
                },
            )

        self._requests[client_ip].append(now)
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining - 1)
        response.headers["X-RateLimit-Reset"] = str(window_end)
        return response

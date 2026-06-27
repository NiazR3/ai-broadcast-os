"""
Auth middleware & rate limiter for QuantAI.

Two layers:
  1. get_current_user — FastAPI dependency that extracts user from JWT
  2. RateLimiter     — in-memory sliding-window rate limiter per user

Usage:
    @router.get("/protected")
    async def protected(user: dict = Depends(get_current_user)):
        ...

    @router.get("/limited")
    async def limited(request: Request, user: dict = Depends(get_current_user)):
        await rate_limiter.check(request, user)
        ...
"""

from __future__ import annotations

import time
from typing import Optional

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend import config
from backend.services.user_service import verify_token

_security = HTTPBearer(auto_error=False)


# ── Tier helpers ──


def _infer_tier(user: Optional[dict]) -> str:
    """Determine plan tier from user metadata.  Defaults to 'free'."""
    if user is None:
        return "free"

    # Check for app_metadata for plan tier
    meta = user.get("app_metadata", {}) or {}
    user_meta = user.get("user_metadata", {}) or {}

    tier = (
        meta.get("plan")
        or user_meta.get("plan")
        or "free"
    )
    return tier if tier in ("free", "pro") else "free"


def _rate_limit_for_tier(tier: str) -> int:
    """Requests per minute for the given tier."""
    return config.PRO_RATE_LIMIT if tier == "pro" else config.FREE_RATE_LIMIT


# ── Dependency: resolve current user from Bearer token ──


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_security),
) -> Optional[dict]:
    """
    FastAPI dependency — returns user dict or None.
    Returns None (not 401) when unauthenticated so endpoints can still
    serve anonymous requests with free-tier limits.

    Raise on invalid token so the client knows to re-authenticate.
    """
    if credentials is None:
        return None  # anonymous

    user = verify_token(credentials.credentials)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user["_tier"] = _infer_tier(user)
    user["_token"] = credentials.credentials
    return user


# ── Rate limiter ──


class RateLimiter:
    """
    In-memory sliding-window rate limiter.

    Tracks request timestamps per user_id in a dict.  Old entries are
    pruned opportunistically on each check.  Not persisted across restarts
    (fine for MVP — swap for Redis later).
    """

    def __init__(self):
        self._buckets: dict[str, list[float]] = {}
        self._window_s = 60  # 1-minute window

    async def check(self, request: Request, user: Optional[dict] = None):
        """
        Raise 429 if the user has exceeded their rate limit.
        Anonymous users are keyed by client IP.
        """
        user_id = user.get("id") if user else None
        key = user_id or request.client.host if request.client else "unknown"
        tier = user.get("_tier", "free") if user else "free"
        limit = _rate_limit_for_tier(tier)

        now = time.time()
        window = self._window_s

        # Prune stale entries
        bucket = self._buckets.setdefault(key, [])
        self._buckets[key] = [ts for ts in bucket if now - ts < window]

        if len(self._buckets[key]) >= limit:
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "Rate limit exceeded",
                    "limit": limit,
                    "window_seconds": window,
                    "tier": tier,
                },
            )

        self._buckets[key].append(now)


rate_limiter = RateLimiter()

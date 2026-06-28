"""Simple API key authentication for the Broadcast service."""

import logging

from fastapi import Header, HTTPException

from broadcast.config import Settings

logger = logging.getLogger(__name__)

_settings_cache: Settings | None = None


def _get_settings() -> Settings:
    """Lazy-load settings to avoid circular imports at module level."""
    global _settings_cache
    if _settings_cache is None:
        _settings_cache = Settings()
    return _settings_cache


async def verify_api_key(x_api_key: str | None = Header(None)) -> None:
    """Dependency that validates the X-API-Key header.

    If BROADCAST_API_KEY is not configured (empty string), authentication
    is skipped (development mode). If configured, the request MUST include
    a matching X-API-Key header.

    Raises:
        HTTPException(401): If the header is missing.
        HTTPException(403): If the header value does not match.
    """
    settings = _get_settings()
    if not settings.api_key:
        return  # No key configured = no auth required (development mode)

    if not x_api_key:
        raise HTTPException(status_code=401, detail="Missing X-API-Key header")

    if x_api_key != settings.api_key:
        raise HTTPException(status_code=403, detail="Invalid API key")

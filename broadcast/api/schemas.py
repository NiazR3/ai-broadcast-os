"""Pydantic models for the Broadcast API."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, field_validator

from broadcast.validation import validate_stream_key


class PlatformConfigResponse(BaseModel):
    """Response model for platform streaming status."""

    streaming: bool
    rtmp_url: str = ""
    error: Optional[str] = None


class BroadcastStatusResponse(BaseModel):
    """Response model for overall broadcast status."""

    active: bool
    uptime_seconds: int = 0
    platforms: dict[str, PlatformConfigResponse]


class PlatformUpdateRequest(BaseModel):
    """Request model for updating platform stream keys."""

    twitch: str = ""
    youtube: str = ""
    facebook: str = ""

    @field_validator("twitch", "youtube", "facebook")
    @classmethod
    def _validate_stream_keys(cls, v: str) -> str:
        return validate_stream_key(v)


class SceneListResponse(BaseModel):
    scenes: list[str]


class ErrorResponse(BaseModel):
    detail: str

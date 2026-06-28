"""Broadcast control API endpoints."""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, HTTPException

from broadcast.api.schemas import (
    BroadcastStatusResponse,
    PlatformConfigResponse,
    PlatformUpdateRequest,
    SceneListResponse,
)
from broadcast.config import Settings
from broadcast.obs.controller import ObsController, ObsConnectionError
from broadcast.streaming.multiplexer import Multiplexer
from broadcast.streaming.platforms import Platform, build_rtmp_url

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/broadcast", tags=["broadcast"])

_settings = Settings()
_obs = ObsController(
    host=_settings.obs_host,
    port=_settings.obs_port,
    password=_settings.obs_password,
)
_mux = Multiplexer(_settings)


def _build_platform_responses(status) -> dict[str, PlatformConfigResponse]:
    """Convert platform statuses to API response models."""
    return {
        name: PlatformConfigResponse(
            streaming=ps.streaming,
            rtmp_url=ps.rtmp_url,
            error=ps.error,
        )
        for name, ps in status.platforms.items()
    }


@router.get("/status", response_model=BroadcastStatusResponse)
def get_status():
    """Get current broadcast status."""
    s = _mux.status
    return BroadcastStatusResponse(
        active=s.active,
        uptime_seconds=s.uptime_seconds,
        platforms=_build_platform_responses(s),
    )


@router.post("/start", response_model=BroadcastStatusResponse)
def start_broadcast():
    """Start broadcasting to all configured platforms."""
    _mux.start_broadcast()
    return get_status()


@router.post("/stop", response_model=BroadcastStatusResponse)
def stop_broadcast():
    """Stop broadcasting."""
    _mux.stop_broadcast()
    return get_status()


@router.get("/scenes", response_model=SceneListResponse)
def list_scenes():
    """List available OBS scenes."""
    try:
        result = asyncio.run(_obs.get_scene_list())
        return SceneListResponse(scenes=result)
    except ObsConnectionError:
        raise HTTPException(status_code=503, detail="OBS not connected")
    except Exception as exc:
        logger.exception("Failed to list OBS scenes")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/scenes/{scene_name}")
def switch_scene(scene_name: str):
    """Switch to a named OBS scene."""
    try:
        asyncio.run(_obs.switch_scene(scene_name))
        return {"scene": scene_name, "status": "switched"}
    except ObsConnectionError:
        raise HTTPException(status_code=503, detail="OBS not connected")
    except Exception as exc:
        logger.exception("Failed to switch OBS scene")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/platforms")
def get_platforms():
    """Get current platform configuration."""
    return _build_platform_responses(_mux.status)


@router.post("/platforms")
def update_platforms(req: PlatformUpdateRequest):
    """Update stream keys and reconfigure platforms."""
    updates = {"twitch": req.twitch, "youtube": req.youtube, "facebook": req.facebook}
    for name, key in updates.items():
        if name not in _mux.status.platforms:
            continue
        ps = _mux.status.platforms[name]
        if key:
            try:
                plat = Platform(name)
                ps.rtmp_url = build_rtmp_url(plat, key)
                ps.error = None
            except ValueError as exc:
                ps.error = str(exc)
                ps.rtmp_url = ""
        else:
            ps.rtmp_url = ""
            ps.error = "Stream key not configured"
        ps.streaming = False
    return get_platforms()

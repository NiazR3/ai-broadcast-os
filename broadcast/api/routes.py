"""Broadcast control API endpoints."""

from __future__ import annotations

import asyncio
import logging
from time import time

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect

from broadcast.api.schemas import (
    BroadcastStatusResponse,
    PlatformConfigResponse,
    PlatformUpdateRequest,
    SceneListResponse,
)
from broadcast.config import Settings
from broadcast.events.bus import EventBus
from broadcast.obs.controller import ObsController, ObsConnectionError
from broadcast.streaming.multiplexer import Multiplexer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/broadcast", tags=["broadcast"])

_settings = Settings()
_obs = ObsController(
    host=_settings.obs_host,
    port=_settings.obs_port,
    password=_settings.obs_password,
)
_mux = Multiplexer(_settings)
_event_bus = EventBus()


def get_mux() -> Multiplexer:
    """Return the module-level Multiplexer instance."""
    return _mux


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


def _publish_event(event_type: str, **extra) -> None:
    """Publish a broadcast event asynchronously."""
    asyncio.create_task(_event_bus.publish("broadcast", {
        "type": event_type,
        "timestamp": time(),
        **extra,
    }))


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
async def start_broadcast():
    """Start broadcasting to all configured platforms."""
    _mux.start_broadcast()
    _publish_event("broadcast.started")
    return get_status()


@router.post("/stop", response_model=BroadcastStatusResponse)
async def stop_broadcast():
    """Stop broadcasting."""
    _mux.stop_broadcast()
    _publish_event("broadcast.stopped")
    return get_status()


@router.get("/scenes", response_model=SceneListResponse)
async def list_scenes():
    """List available OBS scenes."""
    try:
        result = await _obs.get_scene_list()
        return SceneListResponse(scenes=result)
    except ObsConnectionError:
        raise HTTPException(status_code=503, detail="OBS not connected")
    except Exception as exc:
        logger.exception("Failed to list OBS scenes")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/scenes/{scene_name}")
async def switch_scene(scene_name: str):
    """Switch to a named OBS scene."""
    try:
        await _obs.switch_scene(scene_name)
        _publish_event("scene.switched", scene=scene_name)
        return {"scene": scene_name, "status": "switched"}
    except ObsConnectionError:
        raise HTTPException(status_code=503, detail="OBS not connected")
    except Exception as exc:
        logger.exception("Failed to switch OBS scene")
        raise HTTPException(status_code=500, detail=str(exc))


@router.websocket("/ws")
async def broadcast_events(websocket: WebSocket):
    """WebSocket endpoint for real-time broadcast events."""
    await websocket.accept()
    try:
        async for event in _event_bus.subscribe("broadcast"):
            await websocket.send_json(event)
    except WebSocketDisconnect:
        pass


@router.get("/platforms", response_model=dict[str, PlatformConfigResponse])
def get_platforms():
    """Get current platform configuration."""
    return _build_platform_responses(_mux.status)


@router.post("/platforms")
async def update_platforms(req: PlatformUpdateRequest):
    """Update stream keys and reconfigure platforms."""
    updates = {"twitch": req.twitch, "youtube": req.youtube, "facebook": req.facebook}
    for name, key in updates.items():
        _mux.update_platform(name, key)
        status = _mux.status.platforms.get(name)
        if status is None:
            continue
        if status.error:
            if key:
                _publish_event("platform.error", platform=name, error=status.error)
            else:
                _publish_event("platform.disconnected", platform=name, error=status.error)
        else:
            _publish_event("platform.connected", platform=name)
    return get_platforms()

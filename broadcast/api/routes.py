"""Broadcast control API endpoints."""

from __future__ import annotations

import asyncio
import logging
from time import time

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect

from broadcast.api.schemas import (
    BroadcastStatusResponse,
    PlatformConfigResponse,
    PlatformUpdateRequest,
    SceneListResponse,
    SceneSourceResponse,
    SourceToggleResponse,
)
from broadcast.auth import verify_api_key
from broadcast.config import Settings
from broadcast.events.bus import EventBus
from broadcast.obs.controller import ObsController, ObsConnectionError
from broadcast.streaming.multiplexer import Multiplexer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/broadcast", tags=["broadcast"], dependencies=[Depends(verify_api_key)])

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
        await _obs.connect()
        result = await _obs.get_scene_list()
        return SceneListResponse(scenes=result)
    except ObsConnectionError:
        raise HTTPException(status_code=503, detail="OBS not connected")
    except Exception:
        logger.exception("Failed to list OBS scenes")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/scenes/{scene_name}")
async def switch_scene(scene_name: str):
    """Switch to a named OBS scene."""
    try:
        await _obs.connect()
        await _obs.switch_scene(scene_name)
        _publish_event("scene.switched", scene=scene_name)
        return {"scene": scene_name, "status": "switched"}
    except ObsConnectionError:
        raise HTTPException(status_code=503, detail="OBS not connected")
    except Exception:
        logger.exception("Failed to switch OBS scene")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/scenes/{scene_name}/sources", response_model=list[SceneSourceResponse])
async def list_scene_sources(scene_name: str):
    """List all sources in a named OBS scene."""
    try:
        await _obs.connect()
        sources = await _obs.get_scene_sources(scene_name)
        return [SceneSourceResponse(**s) for s in sources]
    except ObsConnectionError:
        raise HTTPException(status_code=503, detail="OBS not connected")
    except Exception:
        logger.exception("Failed to list OBS scene sources")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/scenes/{scene_name}/sources/{source_id}/toggle", response_model=SourceToggleResponse)
async def toggle_source_visibility(scene_name: str, source_id: int):
    """Toggle a source's visibility on/off in a named OBS scene."""
    try:
        await _obs.connect()
        sources = await _obs.get_scene_sources(scene_name)
        match = next((s for s in sources if s["id"] == source_id), None)
        if match is None:
            raise HTTPException(status_code=404, detail="Source not found")
        new_enabled = not match["enabled"]
        await _obs.set_source_visibility_in_scene(scene_name, source_id, new_enabled)
        return SourceToggleResponse(source_id=source_id, enabled=new_enabled)
    except HTTPException:
        raise
    except ObsConnectionError:
        raise HTTPException(status_code=503, detail="OBS not connected")
    except Exception:
        logger.exception("Failed to toggle OBS source visibility")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.websocket("/ws")
async def broadcast_events(websocket: WebSocket):
    """WebSocket endpoint for real-time broadcast events."""
    # Validate Origin header against allowed origins.
    # Empty origin (no header) is allowed for non-browser clients (test tools, wscat, curl).
    # Browsers always send Origin, so browser-based connections are validated.
    origin = websocket.headers.get("origin", "")
    allowed_origins = _settings.websocket_allowed_origins
    if origin and allowed_origins and origin not in allowed_origins:
        logger.warning("WebSocket connection rejected: origin '%s' not allowed", origin)
        await websocket.close(code=1008)  # Policy violation
        return

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

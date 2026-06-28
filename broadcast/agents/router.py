"""Agent API endpoints — control the producer, director, host, and co-host agents."""

from __future__ import annotations

import asyncio
import logging
from time import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from broadcast.config import Settings
from broadcast.events.bus import EventBus

from broadcast.agents.dialogue import HostAgent, CoHostAgent
from broadcast.agents.director import DirectorAgent
from broadcast.agents.models import (
    EpisodeScript, Segment, SegmentType,
    DialogueBlock, DialogueLine,
)
from broadcast.agents.producer import ProducerAgent
from broadcast.auth import verify_api_key

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent", tags=["agent"], dependencies=[Depends(verify_api_key)])

# Module-level singletons (following M1 pattern)
_producer = ProducerAgent()
_director = DirectorAgent()
_host = HostAgent()
_cohost = CoHostAgent()
_event_bus = EventBus()
_settings = Settings()


def _publish_agent_event(event_type: str, **extra) -> None:
    """Publish an agent event asynchronously.

    Handles both async contexts (running event loop) and sync contexts
    (e.g. thread pool where no event loop exists).
    """
    payload = {
        "type": event_type,
        "timestamp": time(),
        **extra,
    }
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # No running loop — create a temporary one (sync endpoint in thread pool)
        asyncio.run(_event_bus.publish("broadcast", payload))
    else:
        loop.create_task(_event_bus.publish("broadcast", payload))


# ── Episode endpoints ──────────────────────────────────────────────

@router.post("/episode")
def create_episode(body: dict) -> dict:
    """Create a new episode script."""
    title = body.get("title", "").strip()
    if not title:
        raise HTTPException(status_code=422, detail="Episode title is required")
    script = _producer.create_episode(title)
    return script.model_dump()


@router.get("/episodes")
def list_episodes() -> list[dict]:
    """List all created episodes."""
    return [s.model_dump() for s in _producer.list_episodes()]


@router.get("/episode/{script_id}")
def get_episode(script_id: str) -> dict:
    """Get an episode by its ID."""
    script = _producer.get_episode(script_id)
    if script is None:
        raise HTTPException(status_code=404, detail="Episode not found")
    return script.model_dump()


@router.post("/episode/{script_id}/segment")
def add_segment(script_id: str, body: dict) -> dict:
    """Add a segment to an episode."""
    script = _producer.get_episode(script_id)
    if script is None:
        raise HTTPException(status_code=404, detail="Episode not found")

    seg_type = body.get("type", "content")
    if seg_type not in (t.value for t in SegmentType):
        raise HTTPException(status_code=422, detail=f"Invalid segment type: {seg_type}")

    segment = Segment(
        id=body.get("id", f"seg_{len(script.segments)}"),
        type=SegmentType(seg_type),
        title=body.get("title", "Untitled"),
        duration_seconds=body.get("duration_seconds", 60),
        scene_name=body.get("scene_name", ""),
        dialogue_prompt=body.get("dialogue_prompt", ""),
    )
    updated = _producer.add_segment(script, segment)
    return updated.model_dump()


# ── Director endpoints ─────────────────────────────────────────────

@router.get("/director/status")
def director_status() -> dict:
    """Get the director's current status."""
    seg = _director.current_segment
    return {
        "running": _director.running,
        "current_segment": seg.model_dump() if seg else None,
        "current_segment_index": _director.current_segment_index,
        "has_more": _director.has_more,
        "script_loaded": _director.script is not None,
        "script_title": _director.script.title if _director.script else None,
    }


@router.post("/episode/{script_id}/load")
def load_episode(script_id: str) -> dict:
    """Load an episode into the director."""
    script = _producer.get_episode(script_id)
    if script is None:
        raise HTTPException(status_code=404, detail="Episode not found")
    if not script.segments:
        raise HTTPException(status_code=422, detail="Episode has no segments")
    _director.load_script(script)
    return {
        "loaded": True,
        "title": script.title,
        "segment_count": len(script.segments),
    }


@router.post("/director/next")
def director_next() -> dict:
    """Advance the director to the next segment."""
    segment = _director.next_segment()
    if segment is None:
        raise HTTPException(status_code=400, detail="No more segments")
    _publish_agent_event("agent.director.segment_started",
        segment_id=segment.id,
        segment_title=segment.title,
        segment_type=segment.type.value,
        duration_seconds=segment.duration_seconds,
    )
    return {
        "segment": segment.model_dump(),
        "segment_index": _director.current_segment_index,
        "has_more": _director.has_more,
    }


@router.post("/director/seek/{segment_id}")
def director_seek(segment_id: str) -> dict:
    """Jump directly to a named segment."""
    segment = _director.seek_to_segment(segment_id)
    if segment is None:
        raise HTTPException(status_code=404, detail="Segment not found")
    return {
        "segment": segment.model_dump(),
        "segment_index": _director.current_segment_index,
        "has_more": _director.has_more,
    }


@router.post("/director/generate")
def director_generate() -> dict:
    """Generate host + co-host dialogue for the current segment."""
    segment = _director.current_segment
    if segment is None:
        raise HTTPException(status_code=400, detail="No segment loaded. Load an episode and advance to a segment.")
    host_block = _host.generate_dialogue(segment)
    cohost_block = _cohost.generate_dialogue(segment, host_block.lines[0].text if host_block.lines else "")
    _publish_agent_event("agent.dialogue.generated",
        segment_id=segment.id,
        host_text=host_block.lines[0].text if host_block.lines else "",
        cohost_text=cohost_block.lines[0].text if cohost_block.lines else "",
    )
    return {
        "segment_id": segment.id,
        "host": host_block.model_dump(),
        "cohost": cohost_block.model_dump(),
    }


# ── Standalone dialogue endpoints (for testing without director) ──

@router.post("/host/dialogue")
def host_dialogue(body: dict) -> dict:
    """Generate host dialogue for a given segment description."""
    segment = Segment(
        id=body.get("id", "custom"),
        type=SegmentType(body.get("type", "content")),
        title=body.get("title", "Untitled"),
        duration_seconds=body.get("duration_seconds", 30),
        scene_name=body.get("scene_name", ""),
        dialogue_prompt=body.get("dialogue_prompt", ""),
    )
    block = _host.generate_dialogue(segment)
    return block.model_dump()


@router.post("/cohost/dialogue")
def cohost_dialogue(body: dict) -> dict:
    """Generate co-host dialogue for a given segment description."""
    segment = Segment(
        id=body.get("id", "custom"),
        type=SegmentType(body.get("type", "content")),
        title=body.get("title", "Untitled"),
        duration_seconds=body.get("duration_seconds", 30),
        scene_name=body.get("scene_name", ""),
        dialogue_prompt=body.get("dialogue_prompt", ""),
    )
    block = _cohost.generate_dialogue(segment)
    return block.model_dump()

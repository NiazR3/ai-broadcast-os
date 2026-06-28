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
from broadcast.agents.persona import PersonaProfile, PersonaRepository, VoiceStyle
from broadcast.agents.director import DirectorAgent
from broadcast.agents.models import (
    AgentType, EpisodeScript, Segment, SegmentType,
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
_persona_repo = PersonaRepository()
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
    index = _director.current_segment_index
    return {
        "running": _director.running,
        "current_segment": seg.model_dump() if seg else None,
        "current_segment_index": index if index >= 0 else None,
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
    if _director.script is None:
        raise HTTPException(status_code=400, detail="No script loaded. Load an episode first.")
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


@router.post("/director/generate")
def director_generate() -> dict:
    """Generate host + co-host dialogue for the current segment."""
    segment = _director.current_segment
    if segment is None:
        raise HTTPException(status_code=400, detail="No segment loaded. Load an episode and advance to a segment.")
    host_block = _host.generate_dialogue(segment, repo=_persona_repo)
    cohost_block = _cohost.generate_dialogue(segment, host_block.lines[0].text if host_block.lines else "", repo=_persona_repo)
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
    block = _host.generate_dialogue(segment, repo=_persona_repo)
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
    block = _cohost.generate_dialogue(segment, repo=_persona_repo)
    return block.model_dump()


# ── Persona CRUD endpoints ─────────────────────────────────────────

@router.get("/personas", tags=["persona"])
def list_personas() -> list[dict]:
    """List all persona profiles."""
    return [p.model_dump() for p in _persona_repo.list()]


@router.post("/personas", tags=["persona"])
def create_persona(body: dict) -> dict:
    """Create a new persona profile."""
    agent_type_str = body.get("agent_type", "host")
    if agent_type_str not in (t.value for t in AgentType):
        raise HTTPException(status_code=422, detail=f"Invalid agent_type: {agent_type_str}")
    voice_str = body.get("voice_style", "casual")
    if voice_str not in (v.value for v in VoiceStyle):
        raise HTTPException(status_code=422, detail=f"Invalid voice_style: {voice_str}")
    try:
        persona = _persona_repo.create(
            name=body.get("name", "").strip(),
            agent_type=AgentType(agent_type_str),
            personality_traits=body.get("personality_traits"),
            catchphrases=body.get("catchphrases"),
            voice_style=VoiceStyle(voice_str),
            default_emotion=body.get("default_emotion", "neutral"),
            emotional_range=body.get("emotional_range"),
            background_story=body.get("background_story", ""),
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return persona.model_dump()


@router.get("/personas/{persona_id}", tags=["persona"])
def get_persona(persona_id: str) -> dict:
    """Get a persona profile by ID."""
    persona = _persona_repo.get(persona_id)
    if persona is None:
        raise HTTPException(status_code=404, detail="Persona not found")
    return persona.model_dump()


@router.put("/personas/{persona_id}", tags=["persona"])
def update_persona(persona_id: str, body: dict) -> dict:
    """Update fields on an existing persona."""
    try:
        persona = _persona_repo.update(persona_id, **body)
    except ValueError:
        raise HTTPException(status_code=404, detail="Persona not found")
    return persona.model_dump()


@router.delete("/personas/{persona_id}", tags=["persona"])
def delete_persona(persona_id: str) -> dict:
    """Delete a persona profile.

    Refuses deletion if the persona is currently assigned to an agent.
    """
    host_pid = getattr(_host, "_persona_id", None)
    cohost_pid = getattr(_cohost, "_persona_id", None)
    if persona_id == host_pid or persona_id == cohost_pid:
        raise HTTPException(
            status_code=409,
            detail="Cannot delete a persona that is currently assigned to an agent",
        )
    if not _persona_repo.delete(persona_id):
        raise HTTPException(status_code=404, detail="Persona not found")
    return {"deleted": True, "persona_id": persona_id}


# ── Persona assignment endpoints ───────────────────────────────────

@router.post("/host/persona/{persona_id}", tags=["persona"])
def assign_host_persona(persona_id: str) -> dict:
    """Assign a persona profile to the Host agent."""
    persona = _persona_repo.get(persona_id)
    if persona is None:
        raise HTTPException(status_code=404, detail="Persona not found")
    _host.assign_persona(persona_id, _persona_repo)
    return {
        "assigned": True,
        "persona_id": persona_id,
        "agent": "host",
        "persona_name": persona.name,
    }


@router.delete("/host/persona", tags=["persona"])
def remove_host_persona() -> dict:
    """Remove the persona from the Host agent (revert to default)."""
    _host.remove_persona()
    return {"removed": True, "agent": "host"}


@router.post("/cohost/persona/{persona_id}", tags=["persona"])
def assign_cohost_persona(persona_id: str) -> dict:
    """Assign a persona profile to the Co-Host agent."""
    persona = _persona_repo.get(persona_id)
    if persona is None:
        raise HTTPException(status_code=404, detail="Persona not found")
    _cohost.assign_persona(persona_id, _persona_repo)
    return {
        "assigned": True,
        "persona_id": persona_id,
        "agent": "cohost",
        "persona_name": persona.name,
    }


@router.delete("/cohost/persona", tags=["persona"])
def remove_cohost_persona() -> dict:
    """Remove the persona from the Co-Host agent (revert to default)."""
    _cohost.remove_persona()
    return {"removed": True, "agent": "cohost"}

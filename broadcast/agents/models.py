"""Pydantic models for agent episode scripts, segments, and dialogue."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class AgentType(str, Enum):
    """Types of agents in the broadcast system."""
    HOST = "host"
    COHOST = "cohost"
    DIRECTOR = "director"
    PRODUCER = "producer"


class SegmentType(str, Enum):
    """Types of show segments."""
    INTRO = "intro"
    CONTENT = "content"
    GUEST = "guest"
    AD = "ad"
    OUTRO = "outro"


class ScriptStatus(str, Enum):
    """Lifecycle status of an episode script."""
    DRAFT = "draft"
    READY = "ready"
    BROADCASTING = "broadcasting"
    COMPLETED = "completed"


class DialogueLine(BaseModel):
    """A single line of dialogue from one speaker."""
    speaker: str = Field(..., description="Speaker name (e.g. 'Host', 'CoHost')")
    text: str = Field(..., min_length=1, description="Dialogue text")
    emotion: Optional[str] = Field(None, description="Emotional tone (e.g. 'excited', 'serious')")
    order: int = Field(default=0, ge=0, description="Line order within the block")


class DialogueBlock(BaseModel):
    """A block of dialogue lines for one segment."""
    segment_id: str = Field(..., description="ID of the segment this dialogue belongs to")
    lines: list[DialogueLine] = Field(..., min_length=1, description="Dialogue lines")

    @field_validator("lines")
    @classmethod
    def lines_must_not_be_empty(cls, v: list[DialogueLine]) -> list[DialogueLine]:
        if not v:
            raise ValueError("DialogueBlock must have at least one line")
        return v


class Segment(BaseModel):
    """A single segment in an episode timeline."""
    id: str = Field(..., description="Unique segment identifier (e.g. 'intro', 'segment_1')")
    type: SegmentType = Field(..., description="Type of segment")
    title: str = Field(..., min_length=1, description="Segment title/headline")
    duration_seconds: int = Field(default=60, ge=0, description="Planned duration in seconds")
    scene_name: str = Field(default="", description="OBS scene to switch to for this segment")
    dialogue_prompt: str = Field(default="", description="Topic/prompt for dialogue generation")
    order: int = Field(default=0, ge=0, description="Display order in the timeline")


class EpisodeScript(BaseModel):
    """Complete episode script with timeline and segments."""
    id: str = Field(default="", description="Unique script ID (auto-generated if empty)")
    title: str = Field(..., min_length=1, description="Episode title")
    segments: list[Segment] = Field(default_factory=list, description="Ordered segment list")
    status: ScriptStatus = Field(default=ScriptStatus.DRAFT, description="Episode lifecycle status")

    @property
    def total_duration(self) -> int:
        """Sum of all segment durations in seconds."""
        return sum(s.duration_seconds for s in self.segments)

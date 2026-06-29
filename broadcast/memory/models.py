"""Pydantic models for memory — personas, guests, interactions, contexts."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class PersonaProfile(BaseModel):
    """A persona profile for an AI broadcast agent."""
    id: str = Field(..., min_length=1)
    agent_type: str = Field(..., min_length=1)  # "host" | "cohost" | "director" | "producer"
    name: str = ""
    personality_traits: dict[str, float] = Field(default_factory=lambda: {"friendly": 0.8, "enthusiastic": 0.7})
    catchphrases: list[str] = Field(default_factory=list)
    voice_style: str = "casual"  # "energetic" | "calm" | "professional" | "casual" | "witty" | "serious"
    default_emotion: str = "neutral"
    emotional_range: list[str] = Field(default_factory=lambda: ["neutral", "happy", "excited"])
    background_story: str = ""
    is_active: bool = True
    usage_count: int = 0
    created_at: float = 0.0
    last_updated: float = 0.0


class GuestProfile(BaseModel):
    """A recurring guest profile with relationship context."""
    id: str = Field(..., min_length=1)
    name: str = ""
    guest_type: str = "one-time"  # "regular" | "special" | "one-time"
    relationship_score: float = 0.0  # -1.0 to 1.0
    topics_of_interest: list[str] = Field(default_factory=list)
    special_notes: str = ""
    appearance_count: int = 0
    last_appearance: Optional[float] = None
    created_at: float = 0.0
    last_updated: float = 0.0


class InteractionEvent(BaseModel):
    """A single interaction recorded during a broadcast session."""
    id: str = Field(..., min_length=1)
    session_id: str = Field(..., min_length=1)
    timestamp: float = 0.0
    event_type: str = Field(..., min_length=1)  # "dialogue" | "reaction" | "correction" | "guest_mention"
    agent_involved: str = ""
    user_involved: str = ""  # "host" | "cohost" | "guest" | "viewer"
    content: str = ""
    outcome: str = "neutral"  # "positive" | "neutral" | "negative"
    metadata: dict = Field(default_factory=dict)


class MemoryContext(BaseModel):
    """Session-level memory context summary."""
    id: str = Field(..., min_length=1)
    session_id: str = Field(..., min_length=1)
    start_time: float = 0.0
    end_time: Optional[float] = None
    participants: list[str] = Field(default_factory=list)
    topics_discussed: list[str] = Field(default_factory=list)
    emotional_arc: list[str] = Field(default_factory=list)
    key_moments: list[str] = Field(default_factory=list)
    feedback_received: list[str] = Field(default_factory=list)

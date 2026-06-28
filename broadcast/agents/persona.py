"""Persona profiles — personality, catchphrases, emotional range for broadcast agents."""
from __future__ import annotations

import uuid
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from broadcast.agents.models import AgentType
from .persona_repository import PersonaRepository


class VoiceStyle(str, Enum):
    """Overall delivery style for a persona."""
    ENERGETIC = "energetic"
    CALM = "calm"
    PROFESSIONAL = "professional"
    CASUAL = "casual"
    WITTY = "witty"
    SERIOUS = "serious"


class PersonaProfile(BaseModel):
    """Defines how a broadcast agent speaks and behaves."""
    id: str = Field(..., description="Unique persona identifier")
    name: str = Field(..., min_length=1, description="Persona display name")
    agent_type: AgentType = Field(..., description="The agent this persona is for")
    personality_traits: list[str] = Field(default_factory=list, description="e.g. enthusiastic, curious")
    catchphrases: list[str] = Field(default_factory=list, description="Catchphrases the persona uses")
    voice_style: VoiceStyle = Field(default=VoiceStyle.CASUAL, description="Delivery style")
    default_emotion: str = Field(default="neutral", description="Fallback emotion for dialogue")
    emotional_range: list[str] = Field(default_factory=list, description="Emotions this persona can express")
    background_story: str = Field(default="", description="Short bio / context for LLM prompt building")


# PersonaRepository is imported from persona_repository to provide optional SQLite persistence.
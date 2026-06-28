"""Persona profiles — personality, catchphrases, emotional range for broadcast agents."""
from __future__ import annotations

import uuid
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from broadcast.agents.models import AgentType


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


class PersonaRepository:
    """In-memory CRUD for persona profiles.

    Follows the same pattern as ProducerAgent._episodes (dict + module-level singleton).
    """

    def __init__(self) -> None:
        self._personas: dict[str, PersonaProfile] = {}

    def _next_id(self) -> str:
        return uuid.uuid4().hex[:12]

    def create(
        self,
        name: str,
        agent_type: AgentType,
        personality_traits: Optional[list[str]] = None,
        catchphrases: Optional[list[str]] = None,
        voice_style: VoiceStyle = VoiceStyle.CASUAL,
        default_emotion: str = "neutral",
        emotional_range: Optional[list[str]] = None,
        background_story: str = "",
    ) -> PersonaProfile:
        """Create a new persona with an auto-generated ID."""
        persona = PersonaProfile(
            id=self._next_id(),
            name=name,
            agent_type=agent_type,
            personality_traits=personality_traits or [],
            catchphrases=catchphrases or [],
            voice_style=voice_style,
            default_emotion=default_emotion,
            emotional_range=emotional_range or [],
            background_story=background_story,
        )
        self._personas[persona.id] = persona
        return persona

    def from_model(self, persona: PersonaProfile) -> PersonaProfile:
        """Store a pre-built PersonaProfile (used for seeding defaults)."""
        self._personas[persona.id] = persona
        return persona

    def get(self, persona_id: str) -> Optional[PersonaProfile]:
        """Get a persona by ID, or None if not found."""
        return self._personas.get(persona_id)

    def list(self) -> list[PersonaProfile]:
        """Return all persona profiles."""
        return list(self._personas.values())

    def update(self, persona_id: str, **kwargs) -> PersonaProfile:
        """Update fields on an existing persona. Raises ValueError if not found."""
        persona = self.get(persona_id)
        if persona is None:
            raise ValueError(f"Persona '{persona_id}' not found")
        for key, value in kwargs.items():
            if hasattr(persona, key) and value is not None:
                setattr(persona, key, value)
        return persona

    def delete(self, persona_id: str) -> bool:
        """Delete a persona. Returns True if existed, False otherwise."""
        if persona_id not in self._personas:
            return False
        del self._personas[persona_id]
        return True

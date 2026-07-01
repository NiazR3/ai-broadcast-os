"""Host and Co-Host agents — template-based dialogue generation.

Dialogue is generated from templates keyed by segment type and topic.
This is the "text flow only" layer; voice synthesis is added in M3.
The template system is designed to be replaced by an LLM-based generator
without changing the agent interface.

M3+: Agents are persona-aware. When a PersonaProfile is assigned,
dialogue lines include emotion tags and occasional catchphrases.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

from broadcast.agents.base import BaseAgent
from broadcast.agents.models import (
    Segment, SegmentType, DialogueLine, DialogueBlock,
)

if TYPE_CHECKING:
    from broadcast.agents.persona import PersonaProfile, PersonaRepository

logger = logging.getLogger(__name__)

# ── Host templates ──────────────────────────────────────────────────

HOST_INTROS = [
    "Welcome back to the show! Today we're diving into {title}.",
    "Hello everyone, and welcome! {title} — that's what we're talking about today.",
    "Hey there, thanks for joining us! {title} is on the agenda.",
]

HOST_CONTENT = [
    "So let's talk about {title}. {prompt}",
    "Moving on to {title}. {prompt}",
    "Alright, {title}. Here's what's happening: {prompt}",
]

HOST_GUEST = [
    "We have a fantastic guest today. Let's welcome them to talk about {title}.",
    "I'm thrilled to introduce our guest for this segment on {title}.",
]

HOST_OUTRO = [
    "That's all for today's show! Thanks for watching, and see you next time.",
    "We're wrapping up. Thank you for being with us — catch you in the next episode!",
    "Before we go, a quick thanks to our viewers. See you next broadcast!",
]

HOST_AD = [
    "We'll be right back after a short break.",
    "Quick pause for a word from our sponsors. Don't go away!",
]

# ── Co-Host templates ──────────────────────────────────────────────

COHOST_CONTENT = [
    "That's a great point! I'd add that {prompt}",
    "You know, that reminds me of something related to {title}. {prompt}",
    "I was reading about {title} just the other day. {prompt}",
]

COHOST_GUEST = [
    "Welcome to the show! We're so excited to have you here to discuss {title}.",
    "Thanks for joining us! {title} is such a fascinating topic.",
]

COHOST_INTROS = [
    "Can't wait to dive into {title}!",
    "Alright, let's get into it — {title} is going to be great!",
    "Looking forward to talking about {title} with everyone!",
]

COHOST_REACTION = [
    "Fascinating! Let's dig deeper into that.",
    "I didn't know that! Tell us more.",
    "Wow, that's really interesting.",
]


class HostAgent(BaseAgent):
    """Host agent — generates opening dialogue, introduces topics, welcomes guests."""

    def __init__(self) -> None:
        super().__init__()
        self._call_counter: dict[str, int] = {}
        self._persona_id: Optional[str] = None

    @property
    def agent_name(self) -> str:
        return "Host"

    @property
    def agent_type(self) -> str:
        return "host"

    # ── Persona management ────────────────────────────────────────

    def assign_persona(self, persona_id: str, repo: "PersonaRepository") -> None:
        """Assign a persona profile to this agent."""
        persona = repo.get(persona_id)
        if persona is None:
            raise ValueError(f"Persona '{persona_id}' not found")
        self._persona_id = persona_id

    def get_persona(self, repo: "PersonaRepository") -> Optional["PersonaProfile"]:
        """Get the currently assigned persona, or None."""
        if self._persona_id is None:
            return None
        return repo.get(self._persona_id)

    def remove_persona(self) -> None:
        """Remove the persona assignment (revert to default behavior)."""
        self._persona_id = None

    # ── Persona helpers ───────────────────────────────────────────

    def _select_emotion(self, persona: "PersonaProfile", segment_type: SegmentType) -> str:
        """Pick an emotion from the persona's range based on segment type."""
        if not persona.emotional_range:
            return persona.default_emotion
        idx_map = {
            SegmentType.INTRO: 0,
            SegmentType.OUTRO: -1,
            SegmentType.AD: 0,
            SegmentType.GUEST: min(1, len(persona.emotional_range) - 1),
            SegmentType.CONTENT: min(1, len(persona.emotional_range) - 1),
        }
        idx = idx_map.get(segment_type, 0)
        return persona.emotional_range[idx]

    def _maybe_inject_catchphrase(self, persona: "PersonaProfile", text: str, key: str) -> str:
        """~20% chance to prepend or append a catchphrase."""
        if not persona.catchphrases:
            return text
        count = self._call_counter.get(f"catchphrase_{key}", 0)
        self._call_counter[f"catchphrase_{key}"] = count + 1
        # Every 5th call gets a catchphrase
        if count % 5 == 0:
            cp = persona.catchphrases[count % len(persona.catchphrases)]
            # Alternate: prepend on even cycles, append on odd
            if count % 2 == 0:
                return f"{cp} {text}"
            else:
                return f"{text} {cp}"
        return text

    # ── Template selection ────────────────────────────────────────

    def _next_template(self, templates: list[str], key: str) -> str:
        """Cycle through templates to add variety."""
        count = self._call_counter.get(key, 0)
        self._call_counter[key] = count + 1
        return templates[count % len(templates)]

    def generate_intro(self, segment: Segment, repo: Optional["PersonaRepository"] = None) -> DialogueBlock:
        """Generate the host's opening for a segment."""
        return self.generate_dialogue(segment, repo)

    def generate_dialogue(self, segment: Segment, repo: Optional["PersonaRepository"] = None) -> DialogueBlock:
        """Generate host dialogue for any segment type, persona-aware."""
        # Base text generation (same logic as before)
        if segment.type == SegmentType.INTRO:
            template = self._next_template(HOST_INTROS, f"intro_{segment.id}")
            text = template.format(title=segment.title, prompt=segment.dialogue_prompt)
        elif segment.type == SegmentType.OUTRO:
            template = self._next_template(HOST_OUTRO, "outro")
            text = template.format(title=segment.title)
        elif segment.type == SegmentType.GUEST:
            template = self._next_template(HOST_GUEST, f"guest_{segment.id}")
            text = template.format(title=segment.title, prompt=segment.dialogue_prompt)
        elif segment.type == SegmentType.AD:
            template = self._next_template(HOST_AD, "ad")
            text = template.format(title=segment.title)
        else:
            # CONTENT or fallback
            template = self._next_template(HOST_CONTENT, f"content_{segment.id}")
            prompt = segment.dialogue_prompt or f"Let's explore {segment.title}."
            text = template.format(title=segment.title, prompt=prompt)

        # Persona enrichment
        emotion = None
        persona = None
        if self._persona_id is not None and repo is not None:
            persona = repo.get(self._persona_id)
        if persona is not None:
            emotion = self._select_emotion(persona, segment.type)
            text = self._maybe_inject_catchphrase(persona, text, segment.id)

        return DialogueBlock(
            segment_id=segment.id,
            lines=[DialogueLine(speaker="Host", text=text, order=0, emotion=emotion)],
        )


class CoHostAgent(BaseAgent):
    """Co-Host agent — adds perspective, reacts, introduces guests."""

    def __init__(self) -> None:
        super().__init__()
        self._call_counter: dict[str, int] = {}
        self._persona_id: Optional[str] = None

    @property
    def agent_name(self) -> str:
        return "Co-Host"

    @property
    def agent_type(self) -> str:
        return "cohost"

    # ── Persona management ────────────────────────────────────────

    def assign_persona(self, persona_id: str, repo: "PersonaRepository") -> None:
        """Assign a persona profile to this agent."""
        persona = repo.get(persona_id)
        if persona is None:
            raise ValueError(f"Persona '{persona_id}' not found")
        self._persona_id = persona_id

    def get_persona(self, repo: "PersonaRepository") -> Optional["PersonaProfile"]:
        """Get the currently assigned persona, or None."""
        if self._persona_id is None:
            return None
        return repo.get(self._persona_id)

    def remove_persona(self) -> None:
        """Remove the persona assignment (revert to default behavior)."""
        self._persona_id = None

    # ── Persona helpers ───────────────────────────────────────────

    def _select_emotion(self, persona: "PersonaProfile", segment_type: SegmentType) -> str:
        """Pick an emotion from the persona's range based on segment type."""
        if not persona.emotional_range:
            return persona.default_emotion
        idx_map = {
            SegmentType.INTRO: 0,
            SegmentType.OUTRO: -1,
            SegmentType.AD: 0,
            SegmentType.GUEST: min(1, len(persona.emotional_range) - 1),
            SegmentType.CONTENT: min(1, len(persona.emotional_range) - 1),
        }
        idx = idx_map.get(segment_type, 0)
        return persona.emotional_range[idx]

    def _maybe_inject_catchphrase(self, persona: "PersonaProfile", text: str, key: str) -> str:
        """~20% chance to prepend or append a catchphrase."""
        if not persona.catchphrases:
            return text
        count = self._call_counter.get(f"catchphrase_{key}", 0)
        self._call_counter[f"catchphrase_{key}"] = count + 1
        if count % 5 == 0:
            cp = persona.catchphrases[count % len(persona.catchphrases)]
            return f"{cp} {text}" if count % 2 == 0 else f"{text} {cp}"
        return text

    # ── Template selection ────────────────────────────────────────

    def _next_template(self, templates: list[str], key: str) -> str:
        """Cycle through templates to add variety."""
        count = self._call_counter.get(key, 0)
        self._call_counter[key] = count + 1
        return templates[count % len(templates)]

    def generate_dialogue(self, segment: Segment, host_dialogue: str = "",
                          repo: Optional["PersonaRepository"] = None) -> DialogueBlock:
        """Generate co-host dialogue riffing on the segment topic and host's cue, persona-aware."""
        lines: list[DialogueLine] = []

        # Base text generation
        if segment.type == SegmentType.INTRO:
            template = self._next_template(COHOST_INTROS, f"intro_{segment.id}")
            text = template.format(title=segment.title)
        elif segment.type == SegmentType.GUEST:
            template = self._next_template(COHOST_GUEST, f"guest_{segment.id}")
            text = template.format(title=segment.title)
        elif segment.type == SegmentType.OUTRO:
            text = "Great show today, everyone! Thanks for tuning in."
        else:
            # CONTENT or fallback — add perspective
            template = self._next_template(COHOST_CONTENT, f"content_{segment.id}")
            prompt = segment.dialogue_prompt or f"there's a lot to say about {segment.title}"
            text = template.format(title=segment.title, prompt=prompt)

        # Persona enrichment for the main line
        emotion = None
        persona = None
        if self._persona_id is not None and repo is not None:
            persona = repo.get(self._persona_id)
        if persona is not None:
            emotion = self._select_emotion(persona, segment.type)
            text = self._maybe_inject_catchphrase(persona, text, segment.id)

        lines.append(DialogueLine(speaker="Co-Host", text=text, order=0, emotion=emotion))

        # Add a reaction line if there was host dialogue
        if host_dialogue and segment.type not in (SegmentType.OUTRO, SegmentType.AD):
            reaction = self._next_template(COHOST_REACTION, f"reaction_{segment.id}")
            react_emotion = None
            if persona is not None:
                idx = min(2, len(persona.emotional_range) - 1) if persona.emotional_range else 0
                react_emotion = persona.emotional_range[idx] if persona.emotional_range else persona.default_emotion
            lines.append(DialogueLine(
                speaker="Co-Host", text=reaction, order=len(lines),
                emotion=react_emotion or "curious",
            ))

        return DialogueBlock(segment_id=segment.id, lines=lines)

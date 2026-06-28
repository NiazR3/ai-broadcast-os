"""Host and Co-Host agents — template-based dialogue generation.

Dialogue is generated from templates keyed by segment type and topic.
This is the "text flow only" layer; voice synthesis is added in M3.
The template system is designed to be replaced by an LLM-based generator
without changing the agent interface.
"""

from __future__ import annotations

import logging
from typing import Optional

from broadcast.agents.base import BaseAgent
from broadcast.agents.models import (
    Segment, SegmentType, DialogueLine, DialogueBlock,
)

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

    @property
    def agent_name(self) -> str:
        return "Host"

    @property
    def agent_type(self) -> str:
        return "host"

    def _next_template(self, templates: list[str], key: str) -> str:
        """Cycle through templates to add variety."""
        count = self._call_counter.get(key, 0)
        self._call_counter[key] = count + 1
        return templates[count % len(templates)]

    def generate_intro(self, segment: Segment) -> DialogueBlock:
        """Generate the host's opening for a segment."""
        template = self._next_template(HOST_INTROS, f"intro_{segment.id}")
        text = template.format(title=segment.title, prompt=segment.dialogue_prompt)
        return DialogueBlock(
            segment_id=segment.id,
            lines=[DialogueLine(speaker="Host", text=text, order=0)],
        )

    def generate_dialogue(self, segment: Segment) -> DialogueBlock:
        """Generate host dialogue for any segment type."""
        if segment.type == SegmentType.INTRO:
            return self.generate_intro(segment)
        elif segment.type == SegmentType.OUTRO:
            template = self._next_template(HOST_OUTRO, "outro")
            text = template.format(title=segment.title)
            return DialogueBlock(
                segment_id=segment.id,
                lines=[DialogueLine(speaker="Host", text=text, order=0)],
            )
        elif segment.type == SegmentType.GUEST:
            template = self._next_template(HOST_GUEST, f"guest_{segment.id}")
            text = template.format(title=segment.title, prompt=segment.dialogue_prompt)
            return DialogueBlock(
                segment_id=segment.id,
                lines=[DialogueLine(speaker="Host", text=text, order=0)],
            )
        elif segment.type == SegmentType.AD:
            template = self._next_template(HOST_AD, "ad")
            text = template.format(title=segment.title)
            return DialogueBlock(
                segment_id=segment.id,
                lines=[DialogueLine(speaker="Host", text=text, order=0)],
            )
        else:
            # CONTENT or fallback
            template = self._next_template(HOST_CONTENT, f"content_{segment.id}")
            prompt = segment.dialogue_prompt or f"Let's explore {segment.title}."
            text = template.format(title=segment.title, prompt=prompt)
            return DialogueBlock(
                segment_id=segment.id,
                lines=[DialogueLine(speaker="Host", text=text, order=0)],
            )


class CoHostAgent(BaseAgent):
    """Co-Host agent — adds perspective, reacts, introduces guests."""

    def __init__(self) -> None:
        super().__init__()
        self._call_counter: dict[str, int] = {}

    @property
    def agent_name(self) -> str:
        return "Co-Host"

    @property
    def agent_type(self) -> str:
        return "cohost"

    def _next_template(self, templates: list[str], key: str) -> str:
        count = self._call_counter.get(key, 0)
        self._call_counter[key] = count + 1
        return templates[count % len(templates)]

    def generate_dialogue(self, segment: Segment, host_dialogue: str = "") -> DialogueBlock:
        """Generate co-host dialogue riffing on the segment topic and host's cue."""
        lines: list[DialogueLine] = []
        if segment.type == SegmentType.INTRO:
            lines.append(DialogueLine(
                speaker="Co-Host", order=0,
                text=f"Can't wait to dive into {segment.title}!",
                emotion="excited",
            ))
        elif segment.type == SegmentType.GUEST:
            template = self._next_template(COHOST_GUEST, f"guest_{segment.id}")
            text = template.format(title=segment.title)
            lines.append(DialogueLine(speaker="Co-Host", text=text, order=0))
        elif segment.type == SegmentType.OUTRO:
            lines.append(DialogueLine(
                speaker="Co-Host", order=0,
                text="Great show today, everyone! Thanks for tuning in.",
            ))
        else:
            # CONTENT or fallback — add perspective
            template = self._next_template(COHOST_CONTENT, f"content_{segment.id}")
            prompt = segment.dialogue_prompt or f"there's a lot to say about {segment.title}"
            text = template.format(title=segment.title, prompt=prompt)
            lines.append(DialogueLine(speaker="Co-Host", text=text, order=0))

        # Add a reaction line if there was host dialogue
        if host_dialogue and segment.type not in (SegmentType.OUTRO, SegmentType.AD):
            reaction = self._next_template(COHOST_REACTION, f"reaction_{segment.id}")
            lines.append(DialogueLine(
                speaker="Co-Host", text=reaction, order=len(lines),
                emotion="curious",
            ))

        return DialogueBlock(segment_id=segment.id, lines=lines)

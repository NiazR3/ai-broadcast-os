"""Producer Agent — episode script creation and management."""

from __future__ import annotations

import logging
import uuid
from typing import Optional

from broadcast.agents.base import BaseAgent
from broadcast.agents.models import EpisodeScript, Segment, ScriptStatus

logger = logging.getLogger(__name__)


class ProducerAgent(BaseAgent):
    """Creates and manages episode scripts with segment timelines."""

    def __init__(self) -> None:
        super().__init__()
        self._episodes: dict[str, EpisodeScript] = {}

    @property
    def agent_name(self) -> str:
        return "Producer"

    @property
    def agent_type(self) -> str:
        return "producer"

    def create_episode(self, title: str) -> EpisodeScript:
        """Create a new episode script with the given title."""
        if not title or not title.strip():
            raise ValueError("Episode title is required")
        script = EpisodeScript(
            id=uuid.uuid4().hex[:12],
            title=title.strip(),
            status=ScriptStatus.DRAFT,
        )
        self._episodes[script.id] = script
        logger.info("Created episode '%s' (ID: %s)", title, script.id)
        return script

    def add_segment(self, script: EpisodeScript, segment: Segment) -> EpisodeScript:
        """Add a segment to an episode script."""
        new_segment = segment.model_copy(update={"order": len(script.segments)})
        script.segments.append(new_segment)
        logger.debug("Added segment '%s' to episode '%s'", segment.id, script.title)
        return script

    def get_episode(self, script_id: str) -> Optional[EpisodeScript]:
        """Retrieve an episode by its ID."""
        return self._episodes.get(script_id)

    def list_episodes(self) -> list[EpisodeScript]:
        """Return all created episodes."""
        return list(self._episodes.values())

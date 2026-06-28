"""Director Agent — episode script timeline navigation.

The Director loads an EpisodeScript and advances segment-by-segment
through the timeline, acting as the cursor for broadcast execution.
"""

from __future__ import annotations

import logging
from typing import Optional

from broadcast.agents.base import BaseAgent
from broadcast.agents.models import EpisodeScript, Segment

logger = logging.getLogger(__name__)


class DirectorAgent(BaseAgent):
    """Navigates an episode script segment-by-segment during broadcast.

    The director acts as a cursor over the episode timeline, advancing
    from one segment to the next. It supports forward navigation,
    seeking, and resetting — without modifying the underlying script.
    """

    def __init__(self) -> None:
        super().__init__()
        self._script: Optional[EpisodeScript] = None
        self._index: int = -1

    # ── Identity ──────────────────────────────────────────────────────

    @property
    def agent_name(self) -> str:
        return "Director"

    @property
    def agent_type(self) -> str:
        return "director"

    # ── Properties ────────────────────────────────────────────────────

    @property
    def script(self) -> Optional[EpisodeScript]:
        """The currently loaded episode script, or None."""
        return self._script

    @property
    def current_segment_index(self) -> int:
        """Index of the current segment (-1 means none selected / before start)."""
        return self._index

    @property
    def current_segment(self) -> Optional[Segment]:
        """The segment at the current index, or None."""
        if self._script is None or self._index < 0:
            return None
        segments = self._script.segments
        if self._index < len(segments):
            return segments[self._index]
        return None

    @property
    def has_more(self) -> bool:
        """True when there are more segments to consume (cursor not past end).

        False when no script is loaded, the script has no segments,
        or the cursor is on or past the last segment.
        """
        if self._script is None:
            return False
        if not self._script.segments:
            return False
        return self._index < len(self._script.segments) - 1

    # ── Navigation ────────────────────────────────────────────────────

    def load_script(self, script: EpisodeScript) -> None:
        """Load an episode script and reset the cursor to before the start.

        Args:
            script: The episode script to navigate.
        """
        self._script = script
        self._index = -1
        logger.info(
            "Loaded script '%s' (%s) with %d segment(s)",
            script.title, script.id, len(script.segments),
        )

    def next_segment(self) -> Optional[Segment]:
        """Advance to the next segment and return it.

        Returns None if already past the end, no script is loaded,
        or the script has no segments.
        """
        if self._script is None:
            return None

        segments = self._script.segments
        if not segments:
            return None

        next_idx = self._index + 1
        if next_idx >= len(segments):
            self._index = next_idx
            logger.debug("Past end of script '%s'", self._script.title)
            return None

        self._index = next_idx
        segment = segments[self._index]
        logger.debug(
            "Advanced to segment %d/%d: '%s'",
            self._index + 1, len(segments), segment.title,
        )
        return segment

    def seek_to_segment(self, segment_id: str) -> Optional[Segment]:
        """Jump to a specific segment by its ID and return it.

        Returns None if the segment ID is not found, no script is loaded,
        or the script has no segments. The cursor position is unchanged
        when the segment is not found.

        Args:
            segment_id: The ID of the target segment.
        """
        if self._script is None:
            return None

        segments = self._script.segments
        if not segments:
            self._index = -1
            return None

        for i, seg in enumerate(segments):
            if seg.id == segment_id:
                self._index = i
                return seg

        return None

    def reset(self) -> None:
        """Reset the cursor to before the first segment (index -1).

        The loaded script is preserved. Safe to call even without
        a loaded script.
        """
        self._index = -1
        logger.debug("Director reset to start of '%s'", getattr(self._script, "title", "None"))

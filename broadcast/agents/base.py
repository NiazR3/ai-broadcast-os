"""Abstract base class for all broadcast agents."""

from __future__ import annotations

import abc
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class BaseAgent(abc.ABC):
    """Abstract base for all AI broadcast agents.

    Provides lifecycle management (start/stop) and agent identity.
    Subclasses must implement agent_name and agent_type properties.
    """

    def __init__(self) -> None:
        self._running = False

    @property
    @abc.abstractmethod
    def agent_name(self) -> str:
        """Human-readable agent name (e.g. 'Host', 'Producer')."""

    @property
    @abc.abstractmethod
    def agent_type(self) -> str:
        """Agent type identifier (e.g. 'host', 'director')."""

    @property
    def running(self) -> bool:
        """Whether the agent is currently active."""
        return self._running

    def start(self) -> None:
        """Start the agent. Idempotent — safe to call multiple times."""
        if self._running:
            logger.debug("%s agent already running", self.agent_name)
            return
        self._running = True
        logger.info("%s agent started", self.agent_name)

    def stop(self) -> None:
        """Stop the agent. Idempotent — safe to call multiple times."""
        if not self._running:
            logger.debug("%s agent already stopped", self.agent_name)
            return
        self._running = False
        logger.info("%s agent stopped", self.agent_name)

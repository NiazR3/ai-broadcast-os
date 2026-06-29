"""Audience Agent — bridges chat, moderation, and polls into the broadcast loop.

Subscribes to EventBus for audience events and provides methods for
the director and dialogue agents to access audience context.
"""

from __future__ import annotations

import asyncio
import logging
from time import time
from typing import Optional

from broadcast.agents.base import BaseAgent
from broadcast.audience.chat import ChatRepository, MockChatBridge
from broadcast.audience.models import (
    ChatActivity, ChatMessage, ChatPlatform, ModerationAction,
)
from broadcast.audience.moderation import ModerationEngine
from broadcast.audience.polls import PollEngine
from broadcast.events.bus import EventBus

logger = logging.getLogger(__name__)


class AudienceAgent(BaseAgent):
    """Tracks audience activity — chat, moderation, and polls.

    Provides a unified interface for the broadcast system to query:
    - Recent chat messages (for dialogue awareness)
    - Active poll results (for on-air announcements)
    - Aggregated activity stats
    """

    def __init__(self, event_bus: Optional[EventBus] = None) -> None:
        super().__init__()
        self._event_bus = event_bus or EventBus()
        self._chat_repo = ChatRepository()
        self._moderation = ModerationEngine()
        self._polls = PollEngine()
        self._simulation: Optional[MockChatBridge] = None
        self._simulation_task: Optional[asyncio.Task] = None

    @property
    def agent_name(self) -> str:
        return "Audience"

    @property
    def agent_type(self) -> str:
        return "audience"

    @property
    def chat_repo(self) -> ChatRepository:
        return self._chat_repo

    @property
    def moderation(self) -> ModerationEngine:
        return self._moderation

    @property
    def polls(self) -> PollEngine:
        return self._polls

    # ── Chat querying ───────────────────────────────────────────────

    def get_recent_chat(self, count: int = 5) -> list[ChatMessage]:
        """Get the most recent chat messages (non-moderated only)."""
        all_msgs = self._chat_repo.recent(count * 2)
        clean = [m for m in all_msgs if not m.moderated]
        return clean[:count]

    def get_flagged_messages(self) -> list[ChatMessage]:
        """Get messages awaiting moderation action."""
        return self._chat_repo.flagged()

    # ── Poll querying ───────────────────────────────────────────────

    def get_poll_results(self) -> Optional[dict]:
        """Get the latest closed poll results, or None."""
        closed = [p for p in self._polls.list_polls(include_closed=True)
                  if p.status.value == "closed"]
        if not closed:
            return None
        latest = max(closed, key=lambda p: p.closed_at or 0)
        return self._polls.get_results(latest.id)

    def get_active_poll(self):
        """Get the currently active poll."""
        return self._polls.get_active_poll()

    # ── Activity stats ──────────────────────────────────────────────

    def get_activity_summary(self) -> ChatActivity:
        """Get aggregated chat statistics."""
        all_msgs = self._chat_repo.recent(500)
        if not all_msgs:
            return ChatActivity()
        unique_users = len(set(m.user.id for m in all_msgs))
        now = time()
        recent_window = [m for m in all_msgs if now - m.timestamp < 60]
        mpm = len(recent_window)
        # Top chatters
        user_counts: dict[str, int] = {}
        for m in all_msgs:
            user_counts[m.user.display_name] = user_counts.get(m.user.display_name, 0) + 1
        top = sorted(user_counts.items(), key=lambda x: -x[1])[:5]
        return ChatActivity(
            total_messages=len(all_msgs),
            unique_users=unique_users,
            messages_per_minute=mpm,
            top_chatters=[{"user": u, "count": c} for u, c in top],
        )

    # ── Chat ingestion ──────────────────────────────────────────────

    def ingest_message(self, message: ChatMessage) -> None:
        """Ingest a chat message through moderation and storage."""
        action = self._moderation.check(message)
        if action is not None:
            message.moderated = True
            message.moderation_action = action.value
        self._chat_repo.add(message)
        # Publish to EventBus
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            asyncio.run(self._event_bus.publish("audience.chat", {
                "type": "audience.chat.message",
                "message_id": message.id,
                "user": message.user.display_name,
                "text": message.text[:100],
                "platform": message.platform.value,
                "moderated": message.moderated,
                "timestamp": message.timestamp,
            }))
        else:
            loop.create_task(self._event_bus.publish("audience.chat", {
                "type": "audience.chat.message",
                "message_id": message.id,
                "user": message.user.display_name,
                "text": message.text[:100],
                "platform": message.platform.value,
                "moderated": message.moderated,
                "timestamp": message.timestamp,
            }))

    # ── Simulation ──────────────────────────────────────────────────

    async def start_simulation(self, rate: float = 0.33) -> None:
        """Start mock chat simulation."""
        if self._simulation is not None:
            logger.warning("Simulation already running")
            return
        bridge = MockChatBridge(rate=rate)
        bridge.start()
        self._simulation = bridge

        loop = asyncio.get_running_loop()
        self._simulation_task = loop.create_task(self._run_simulation())
        logger.info("Chat simulation started at %.2f msg/s", rate)

    async def _run_simulation(self) -> None:
        """Consume simulated chat messages and ingest them."""
        try:
            async for msg in self._simulation.subscribe():
                self.ingest_message(msg)
        except Exception:
            logger.exception("Simulation error")

    def stop_simulation(self) -> None:
        """Stop mock chat simulation."""
        if self._simulation:
            self._simulation.stop()
            self._simulation = None
        if self._simulation_task:
            self._simulation_task.cancel()
            self._simulation_task = None
        logger.info("Chat simulation stopped")

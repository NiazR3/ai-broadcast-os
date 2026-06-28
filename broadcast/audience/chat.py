"""Chat repository — in-memory ring buffer for chat messages."""

from __future__ import annotations

import logging
from time import time
from typing import Optional

from broadcast.audience.models import ChatMessage, ModerationAction

logger = logging.getLogger(__name__)

MAX_MESSAGES = 500


class ChatRepository:
    """In-memory ring buffer for chat messages, capped at MAX_MESSAGES."""

    def __init__(self) -> None:
        self._messages: dict[str, ChatMessage] = {}
        self._order: list[str] = []
        self._flagged: dict[str, ChatMessage] = {}

    def add(self, message: ChatMessage) -> None:
        """Add a message, evicting oldest if at capacity."""
        if message.id in self._messages:
            return
        self._messages[message.id] = message
        self._order.append(message.id)
        if message.moderated and message.moderation_action == ModerationAction.FLAG.value:
            self._flagged[message.id] = message
        if len(self._order) > MAX_MESSAGES:
            oldest = self._order.pop(0)
            self._messages.pop(oldest, None)
            self._flagged.pop(oldest, None)

    def recent(self, limit: int = 50) -> list[ChatMessage]:
        """Get the most recent messages (newest first)."""
        ids = self._order[-limit:]
        results = [self._messages[mid] for mid in ids if mid in self._messages]
        results.reverse()
        return results

    def by_user(self, user_id: str) -> list[ChatMessage]:
        """Get all messages from a specific user."""
        return [m for m in self._messages.values() if m.user.id == user_id]

    def flagged(self) -> list[ChatMessage]:
        """Get all flagged messages awaiting action."""
        return list(self._flagged.values())

    def update_moderation(self, message_id: str, action: str) -> bool:
        """Update moderation status on a message. Returns True if found."""
        msg = self._messages.get(message_id)
        if msg is None:
            return False
        msg.moderated = True
        msg.moderation_action = action
        self._flagged.pop(message_id, None)
        return True

    def count(self) -> int:
        """Current number of stored messages."""
        return len(self._messages)

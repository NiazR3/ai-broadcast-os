"""Chat repository — in-memory ring buffer for chat messages."""

from __future__ import annotations

import asyncio
import logging
import random
from abc import ABC, abstractmethod
from time import time
from typing import AsyncIterator, Optional

from broadcast.audience.models import (
    ChatMessage, ChatPlatform, ChatUser, ChatUserRole, ModerationAction,
)

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


# ── Mock viewer personas ──────────────────────────────────────────────

MOCK_VIEWER_PERSONAS: list[dict] = [
    {"id": "viewer_1", "name": "TechFan42", "role": ChatUserRole.VIEWER,
     "messages": ["Great show today!", "Can you talk about the tech stack?", "Love this content!"]},
    {"id": "viewer_2", "name": "StreamQueen", "role": ChatUserRole.VIP,
     "messages": ["Hello everyone! 🔥", "That's amazing!", "First time watching, this is cool!"]},
    {"id": "viewer_3", "name": "Chatty Cathy", "role": ChatUserRole.VIEWER,
     "messages": ["What do you think about AI?", "I have a question about the setup", "Can you go deeper on that?"]},
    {"id": "viewer_4", "name": "SuperFan99", "role": ChatUserRole.MODERATOR,
     "messages": ["Great segment!", "Love the energy today!", "Keep it up!"]},
    {"id": "viewer_5", "name": "Newbie101", "role": ChatUserRole.VIEWER,
     "messages": ["Just joined, what's this about?", "Hi everyone!", "This looks interesting"]},
    {"id": "viewer_6", "name": "HypeTrain", "role": ChatUserRole.VIEWER,
     "messages": ["LET'S GOOOOO!", "THIS IS AMAZING", "BEST STREAM EVER"]},
    {"id": "viewer_7", "name": "EmojiKing", "role": ChatUserRole.VIEWER,
     "messages": ["🔥🔥🔥", "❤️❤️❤️ This is great ❤️❤️❤️", "😍😍😍😍😍"]},
    {"id": "viewer_8", "name": "SpamBot2024", "role": ChatUserRole.VIEWER,
     "messages": ["CHECK OUT MY STREAM at http://spam.example.com", "BUY NOW!!! http://scam.example.com/best", "FREE MONEY!!! http://free-money.example.com"]},
    {"id": "viewer_9", "name": "CasualGamer", "role": ChatUserRole.VIEWER,
     "messages": ["Nice!", "lol", "gg"]},
]

# ── Default bad words for moderation testing ──────────────────────────

DEFAULT_BAD_WORDS = ["spam", "scam", "fraud", "cheat", "hack", "exploit"]


class ChatBridge(ABC):
    """Abstract base for platform-specific chat bridges."""

    @abstractmethod
    async def subscribe(self) -> AsyncIterator[ChatMessage]:
        """Yield chat messages from a platform as they arrive."""
        ...

    def start(self) -> None:
        """Start the bridge (default no-op). Override if needed."""
        ...

    def stop(self) -> None:
        """Stop the bridge (default no-op). Override if needed."""
        ...


class MockChatBridge(ChatBridge):
    """Generates simulated chat messages for development and testing.

    Cycles through viewer personas, selecting random messages at the
    configured rate. Includes a configurable proportion of spam messages
    to test moderation.
    """

    def __init__(self, rate: float = 0.33, spam_probability: float = 0.1) -> None:
        if rate <= 0:
            raise ValueError("Rate must be positive")
        self._rate = rate
        self._spam_probability = spam_probability
        self._running = False
        self._message_counter = 0

    @property
    def running(self) -> bool:
        return self._running

    def start(self) -> None:
        self._running = True

    def stop(self) -> None:
        self._running = False

    async def subscribe(self) -> AsyncIterator[ChatMessage]:
        """Yield mock messages at the configured rate."""
        self._running = True
        try:
            while self._running:
                self._message_counter += 1
                persona = random.choice(MOCK_VIEWER_PERSONAS)
                text = random.choice(persona["messages"])
                msg = ChatMessage(
                    id=f"mock_{self._message_counter}_{int(time() * 1000)}",
                    platform=ChatPlatform.MOCK,
                    user=ChatUser(
                        id=persona["id"],
                        display_name=persona["name"],
                        platform=ChatPlatform.MOCK,
                        role=persona["role"],
                    ),
                    text=text,
                    timestamp=time(),
                )
                yield msg
                await asyncio.sleep(1.0 / self._rate)
        finally:
            self._running = False

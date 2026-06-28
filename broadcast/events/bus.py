"""In-memory async event bus using asyncio.Queue."""

from __future__ import annotations
import asyncio
from typing import AsyncIterator


class EventBus:
    """Simple pub/sub event bus for in-process broadcast events."""

    def __init__(self) -> None:
        self._subscribers: dict[str, list[asyncio.Queue]] = {}

    async def publish(self, channel: str, data: dict) -> None:
        """Publish an event to all subscribers of a channel."""
        if channel not in self._subscribers:
            return
        dead: list[asyncio.Queue] = []
        for queue in self._subscribers[channel]:
            try:
                queue.put_nowait(data)
            except asyncio.QueueFull:
                dead.append(queue)
        for q in dead:
            self._subscribers[channel].remove(q)

    async def subscribe(self, channel: str) -> AsyncIterator[dict]:
        """Async generator yielding events from a channel."""
        queue: asyncio.Queue = asyncio.Queue(maxsize=256)
        self._subscribers.setdefault(channel, []).append(queue)
        try:
            while True:
                yield await queue.get()
        finally:
            if channel in self._subscribers and queue in self._subscribers[channel]:
                self._subscribers[channel].remove(queue)

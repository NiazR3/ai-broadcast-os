"""Shared event publishing utility — bridges sync/async EventBus publishing.

Used by show_runner.py, router.py, and api/routes.py to publish events
without duplicating the sync/async bridging pattern in each module.
"""

from __future__ import annotations

import asyncio
import logging
from time import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from broadcast.events.bus import EventBus

logger = logging.getLogger(__name__)


def publish_event(event_bus: EventBus, channel: str, event_type: str, **extra) -> None:
    """Publish an event asynchronously via the EventBus.

    Handles both async contexts (with a running event loop) and sync
    contexts (e.g. FastAPI thread pool where no event loop exists).
    Safe to call from any context.

    Args:
        event_bus: The EventBus instance to publish to.
        channel: The event channel (e.g. "broadcast", "research", "media").
        event_type: The event type string (e.g. "show.produced", "show.segment.started").
        **extra: Additional key/value pairs included in the event payload.
    """
    payload = {
        "type": event_type,
        "timestamp": time(),
        **extra,
    }
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        asyncio.run(event_bus.publish(channel, payload))
    else:
        loop.create_task(event_bus.publish(channel, payload))

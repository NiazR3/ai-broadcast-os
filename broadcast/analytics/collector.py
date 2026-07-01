"""EventBus-driven metrics collector — subscribes to broadcast/audience/media events."""

from __future__ import annotations

import asyncio
import logging
from time import time
from typing import Optional

from broadcast.analytics.database import AnalyticsDatabase
from broadcast.analytics.models import AnalyticsEvent, MetricsSnapshot
from broadcast.analytics.session import SessionManager
from broadcast.events.bus import EventBus
from broadcast.monitoring.metrics import (
    analytics_chat_messages_total,
    analytics_collector_up,
    analytics_events_total,
    analytics_snapshots_total,
    broadcast_duration_seconds,
    broadcast_sessions_active,
    broadcast_sessions_total,
)

logger = logging.getLogger(__name__)


class MetricsCollector:
    """Subscribes to EventBus and records metrics to the analytics database.

    Routes events:
    - broadcast.started → session created
    - broadcast.stopped → session closed with aggregates
    - broadcast.* platform events → platform list updated
    - audience.chat.message → message count updated
    - scene.switched, audience.poll.*, media.asset.created → event log
    """

    SNAPSHOT_INTERVAL = 10  # seconds between snapshots while live

    def __init__(
        self,
        db: AnalyticsDatabase,
        event_bus: EventBus,
        session_manager: SessionManager,
    ) -> None:
        self._db = db
        self._event_bus = event_bus
        self._session_manager = session_manager
        self._running = False
        self._chat_count: int = 0
        self._chat_window_start: float = 0.0
        self._broadcast_task: Optional[asyncio.Task] = None
        self._audience_task: Optional[asyncio.Task] = None
        self._snapshot_task: Optional[asyncio.Task] = None
        self._current_session_id: Optional[str] = None
        self._message_counts: dict[str, int] = {}  # user → count
        self._current_viewer_count: int = 0

    @property
    def is_running(self) -> bool:
        return self._running

    def start(self) -> None:
        """Start listening for events. Must be called from an async context."""
        if self._running:
            return
        self._reset_chat_window()

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            logger.warning(
                "MetricsCollector: no running event loop — "
                "call start() from an async context or use FastAPI lifespan"
            )
            return

        self._running = True

        self._broadcast_task = loop.create_task(self._consume("broadcast"))
        self._audience_task = loop.create_task(self._consume("audience.chat"))
        self._snapshot_task = loop.create_task(self._snapshot_loop())
        analytics_collector_up.set(1)
        logger.info("MetricsCollector started")

    def stop(self) -> None:
        """Stop listening for events."""
        self._running = False
        for t in (self._broadcast_task, self._audience_task, self._snapshot_task):
            if t:
                t.cancel()
        self._broadcast_task = None
        self._audience_task = None
        self._snapshot_task = None
        analytics_collector_up.set(0)
        logger.info("MetricsCollector stopped")

    def _reset_chat_window(self) -> None:
        self._chat_count = 0
        self._chat_window_start = time()

    async def _consume(self, channel: str) -> None:
        """Consume events from a single EventBus channel."""
        try:
            async for event in self._event_bus.subscribe(channel):
                if not self._running:
                    break
                self._handle_broadcast_event(event)
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("MetricsCollector consumer error on '%s'", channel)

    def _handle_broadcast_event(self, event: dict) -> None:
        """Route a broadcast event to the appropriate handler."""
        event_type = event.get("type", "")
        if event_type == "broadcast.started":
            self._on_broadcast_started(event)
        elif event_type == "broadcast.stopped":
            self._on_broadcast_stopped()
        elif event_type == "scene.switched":
            self._log_event("scene.switched", {"scene": event.get("scene", "")})
        elif event_type.startswith("platform."):
            self._on_platform_event(event)
        elif event_type.startswith("audience.chat."):
            self._on_chat_event(event)
        elif event_type.startswith("audience.poll."):
            self._log_event(event_type, event)
        elif event_type == "media.asset.created":
            self._log_event(event_type, event)

        # Track every event that reached this handler
        analytics_events_total.labels(event_type=event_type).inc()

    def _on_broadcast_started(self, event: dict) -> None:
        """Handle broadcast start. Guards against duplicate start events."""
        if self._current_session_id is not None:
            logger.warning(
                "Received broadcast.started while session %s is still live; closing it.",
                self._current_session_id,
            )
            self._on_broadcast_stopped()
        platforms = event.get("platforms", [])
        session = self._session_manager.create_session(platforms=platforms)
        self._current_session_id = session.id
        self._reset_chat_window()
        broadcast_sessions_total.inc()
        broadcast_sessions_active.set(1)
        logger.info("Broadcast started, session=%s", session.id)

    def _on_broadcast_stopped(self) -> None:
        """Handle broadcast stop."""
        session_id = self._current_session_id
        if session_id:
            try:
                closed = self._session_manager.close_session(session_id)
                self._take_snapshot(final=True)
                self._current_session_id = None  # Clear after final snapshot
                if closed:
                    broadcast_duration_seconds.observe(closed.duration_seconds)
            except Exception:
                logger.exception(
                    "Failed to properly close session %s", session_id,
                )
        broadcast_sessions_active.set(0)
        logger.info("Broadcast stopped, session=%s closed", session_id)

    def _on_platform_event(self, event: dict) -> None:
        """Handle platform connection/disconnection events."""
        et = event.get("type", "")
        platform = event.get("platform", "")
        if et == "platform.connected":
            self._log_event("platform.connected", {"platform": platform})
        elif et in ("platform.error", "platform.disconnected"):
            self._log_event(et, {"platform": platform, "error": event.get("error", "")})

    def _on_chat_event(self, event: dict) -> None:
        """Handle chat message events."""
        self._chat_count += 1
        analytics_chat_messages_total.inc()
        user = event.get("user", "anonymous")
        self._message_counts[user] = self._message_counts.get(user, 0) + 1

        text = event.get("text", "")
        if len(text) > 100:
            logger.warning("Chat message text truncated from %d to 100 chars for session %s", len(text), self._current_session_id)

        session_id = self._current_session_id
        if session_id:
            self._db.insert_event(AnalyticsEvent(
                id=self._db._next_id("ev"),
                session_id=session_id,
                timestamp=event.get("timestamp", time()),
                event_type="audience.chat.message",
                payload={
                    "user": user,
                    "text": text[:100],
                    "platform": event.get("platform", ""),
                },
            ))

    def set_viewer_count(self, count: int) -> None:
        """Update the current viewer count fed into snapshots."""
        self._current_viewer_count = count

    def _log_event(self, event_type: str, payload: dict) -> None:
        """Record a generic event to the event log."""
        session_id = self._current_session_id
        if not session_id:
            return
        self._db.insert_event(AnalyticsEvent(
            id=self._db._next_id("ev"),
            session_id=session_id,
            timestamp=time(),
            event_type=event_type,
            payload=dict(payload),
        ))

    def _take_snapshot(self, final: bool = False) -> None:
        """Record a metrics snapshot."""
        session_id = self._current_session_id
        if not session_id:
            return

        # Get live metrics from session
        session = self._session_manager.get_session(session_id)
        viewer_count = self._current_viewer_count

        # Compute chat rate (messages/min over the window)
        elapsed = time() - self._chat_window_start
        chat_rate = (self._chat_count / elapsed * 60) if elapsed > 0 else 0.0

        snapshot = MetricsSnapshot(
            id=self._db._next_id("snap"),
            session_id=session_id,
            timestamp=time(),
            viewer_count=viewer_count,
            chat_rate=round(chat_rate, 1),
            platform="all",
        )
        self._db.insert_snapshot(snapshot)
        analytics_snapshots_total.inc()

        # Reset window so the next snapshot measures the next interval
        self._reset_chat_window()

    async def _snapshot_loop(self) -> None:
        """Periodically take snapshots while a session is live."""
        while self._running:
            await asyncio.sleep(self.SNAPSHOT_INTERVAL)
            if self._current_session_id:
                try:
                    self._take_snapshot()
                except Exception:
                    logger.exception("Metrics snapshot failed, continuing loop")

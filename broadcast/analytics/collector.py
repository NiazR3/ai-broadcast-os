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
        self._task: Optional[asyncio.Task] = None
        self._current_session_id: Optional[str] = None
        self._message_counts: dict[str, int] = {}  # user → count

    @property
    def is_running(self) -> bool:
        return self._running

    def start(self) -> None:
        """Start listening for events."""
        if self._running:
            return
        self._running = True
        self._reset_chat_window()

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        self._task = loop.create_task(self._run())
        logger.info("MetricsCollector started")

    def stop(self) -> None:
        """Stop listening for events."""
        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None
        logger.info("MetricsCollector stopped")

    def _reset_chat_window(self) -> None:
        self._chat_count = 0
        self._chat_window_start = time()

    async def _run(self) -> None:
        """Main loop: subscribe to EventBus channels."""
        try:
            async for event in self._event_bus.subscribe("broadcast"):
                if not self._running:
                    break
                self._handle_broadcast_event(event)
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("MetricsCollector error")

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

    def _on_broadcast_started(self, event: dict) -> None:
        """Handle broadcast start."""
        platforms = event.get("platforms", [])
        session = self._session_manager.create_session(platforms=platforms)
        self._current_session_id = session.id
        self._reset_chat_window()
        self._message_counts = {}
        logger.info("Broadcast started, session=%s", session.id)

    def _on_broadcast_stopped(self) -> None:
        """Handle broadcast stop."""
        session_id = self._current_session_id
        if session_id:
            self._session_manager.close_session(session_id)
            self._take_snapshot(final=True)
            self._current_session_id = None
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
        user = event.get("user", "anonymous")
        self._message_counts[user] = self._message_counts.get(user, 0) + 1

        session_id = self._current_session_id
        if session_id:
            self._db.insert_event(AnalyticsEvent(
                id=self._db._next_id("ev"),
                session_id=session_id,
                timestamp=event.get("timestamp", time()),
                event_type="audience.chat.message",
                payload={
                    "user": user,
                    "text": event.get("text", "")[:100],
                    "platform": event.get("platform", ""),
                },
            ))

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
        viewer_count = (session.peak_viewers or 0) if session else 0

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

        if final:
            self._reset_chat_window()

    async def _snapshot_loop(self) -> None:
        """Periodically take snapshots while a session is live."""
        while self._running:
            await asyncio.sleep(self.SNAPSHOT_INTERVAL)
            if self._current_session_id:
                self._take_snapshot()

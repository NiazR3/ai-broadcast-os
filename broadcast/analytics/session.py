"""Broadcast session lifecycle management."""

from __future__ import annotations

import logging
from time import time
from typing import Optional

from broadcast.analytics.database import AnalyticsDatabase
from broadcast.analytics.models import BroadcastSession

logger = logging.getLogger(__name__)


class SessionManager:
    """Manages broadcast session lifecycle — create, update, close."""

    def __init__(self, db: AnalyticsDatabase) -> None:
        self._db = db

    def create_session(self, platforms: Optional[list[str]] = None) -> BroadcastSession:
        """Create a new broadcast session."""
        now = time()
        session = BroadcastSession(
            id=self._db._next_id("sess"),
            started_at=now,
            platforms=platforms or [],
            status="live",
            created_at=now,
        )
        self._db.insert_session(session)
        logger.info("Session created: %s", session.id)
        return session

    def close_session(self, session_id: str) -> Optional[BroadcastSession]:
        """Close a session with computed aggregates."""
        session = self._db.get_session(session_id)
        if session is None:
            logger.warning("Session not found: %s", session_id)
            return None
        if session.status == "ended":
            logger.warning("Session already ended: %s", session_id)
            return session

        agg = self._db.query_aggregates(session_id)
        now = time()
        session.ended_at = now
        session.duration_seconds = now - session.started_at
        session.peak_viewers = agg["peak_viewers"]
        session.avg_viewers = agg["avg_viewers"]
        session.total_chat_messages = agg["total_chat_messages"]
        session.unique_chatters = agg["unique_chatters"]
        session.status = "ended"
        self._db.update_session(session)
        logger.info(
            "Session closed: %s (duration=%.0fs, peak=%d, msgs=%d)",
            session_id, session.duration_seconds, session.peak_viewers,
            session.total_chat_messages,
        )
        return session

    def get_active_session(self) -> Optional[BroadcastSession]:
        """Get the currently live session, if any."""
        return self._db.get_active_session()

    def list_sessions(self, limit: int = 20, status: Optional[str] = None) -> list[BroadcastSession]:
        """List sessions with optional status filter."""
        return self._db.list_sessions(limit=limit, status=status)

    def get_session(self, session_id: str) -> Optional[BroadcastSession]:
        """Get a single session by ID."""
        return self._db.get_session(session_id)

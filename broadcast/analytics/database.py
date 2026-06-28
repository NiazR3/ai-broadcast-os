"""SQLite database wrapper for analytics storage."""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
from time import time
from typing import Optional

from broadcast.analytics.models import (
    AnalyticsEvent,
    AnalyticsReport,
    BroadcastSession,
    EngagementMetrics,
    MetricsSnapshot,
    ReportSummary,
)

logger = logging.getLogger(__name__)


class AnalyticsDatabase:
    """SQLite-backed analytics store.

    Uses WAL mode for concurrent read/write. All timestamps use time.time()
    floats for consistency with the rest of the codebase.
    """

    DB_DIR = "broadcast_data"
    DB_FILENAME = "analytics.db"

    def __init__(self, db_path: Optional[str] = None) -> None:
        self._db_path = db_path or os.path.join(self.DB_DIR, self.DB_FILENAME)
        self._local = threading.local()
        self._lock = threading.Lock()
        self._id_counter: int = 0
        self._ensure_dir()
        self._init_db()

    @property
    def _conn(self) -> sqlite3.Connection:
        """Get thread-local connection."""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(self._db_path)
            self._local.conn.row_factory = sqlite3.Row
            self._local.conn.execute("PRAGMA journal_mode=WAL")
            self._local.conn.execute("PRAGMA foreign_keys=ON")
        return self._local.conn

    def _ensure_dir(self) -> None:
        """Create the database directory if it doesn't exist."""
        db_dir = os.path.dirname(self._db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)

    def _init_db(self) -> None:
        """Create tables and indexes if they don't exist."""
        with self._lock:
            cur = self._conn.cursor()
            cur.executescript("""
                CREATE TABLE IF NOT EXISTS broadcast_sessions (
                    id TEXT PRIMARY KEY,
                    started_at REAL NOT NULL,
                    ended_at REAL,
                    duration_seconds REAL DEFAULT 0,
                    peak_viewers INTEGER DEFAULT 0,
                    avg_viewers REAL DEFAULT 0,
                    total_chat_messages INTEGER DEFAULT 0,
                    unique_chatters INTEGER DEFAULT 0,
                    platforms TEXT DEFAULT '[]',
                    status TEXT DEFAULT 'live',
                    created_at REAL DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS metrics_snapshots (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    viewer_count INTEGER DEFAULT 0,
                    chat_rate REAL DEFAULT 0,
                    platform TEXT DEFAULT 'all',
                    FOREIGN KEY (session_id) REFERENCES broadcast_sessions(id)
                );

                CREATE TABLE IF NOT EXISTS event_log (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    event_type TEXT NOT NULL,
                    payload TEXT DEFAULT '{}',
                    FOREIGN KEY (session_id) REFERENCES broadcast_sessions(id)
                );

                CREATE INDEX IF NOT EXISTS idx_snapshots_session
                    ON metrics_snapshots(session_id);
                CREATE INDEX IF NOT EXISTS idx_events_session
                    ON event_log(session_id);
                CREATE INDEX IF NOT EXISTS idx_events_type
                    ON event_log(event_type);
            """)
            self._conn.commit()

    def _next_id(self, prefix: str = "an") -> str:
        """Generate unique ID with monotonically increasing counter."""
        self._id_counter += 1
        return f"{prefix}_{int(time() * 1000)}_{self._id_counter}"

    # ── Session operations ─────────────────────────────────────────

    def insert_session(self, session: BroadcastSession) -> None:
        with self._lock:
            self._conn.execute(
                """INSERT INTO broadcast_sessions
                   (id, started_at, ended_at, duration_seconds, peak_viewers,
                    avg_viewers, total_chat_messages, unique_chatters,
                    platforms, status, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (session.id, session.started_at, session.ended_at,
                 session.duration_seconds, session.peak_viewers,
                 session.avg_viewers, session.total_chat_messages,
                 session.unique_chatters,
                 json.dumps(session.platforms), session.status,
                 session.created_at),
            )
            self._conn.commit()

    def update_session(self, session: BroadcastSession) -> None:
        with self._lock:
            self._conn.execute(
                """UPDATE broadcast_sessions SET
                   ended_at=?, duration_seconds=?, peak_viewers=?,
                   avg_viewers=?, total_chat_messages=?, unique_chatters=?,
                   platforms=?, status=?
                   WHERE id=?""",
                (session.ended_at, session.duration_seconds,
                 session.peak_viewers, session.avg_viewers,
                 session.total_chat_messages, session.unique_chatters,
                 json.dumps(session.platforms), session.status, session.id),
            )
            self._conn.commit()

    def get_session(self, session_id: str) -> Optional[BroadcastSession]:
        row = self._conn.execute(
            "SELECT * FROM broadcast_sessions WHERE id = ?",
            (session_id,),
        ).fetchone()
        if row is None:
            return None
        return self._row_to_session(row)

    def list_sessions(self, limit: int = 20, status: Optional[str] = None) -> list[BroadcastSession]:
        if status:
            rows = self._conn.execute(
                "SELECT * FROM broadcast_sessions WHERE status = ? ORDER BY created_at DESC LIMIT ?",
                (status, limit),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM broadcast_sessions ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self._row_to_session(r) for r in rows]

    def get_active_session(self) -> Optional[BroadcastSession]:
        row = self._conn.execute(
            "SELECT * FROM broadcast_sessions WHERE status = 'live' ORDER BY created_at DESC LIMIT 1",
        ).fetchone()
        if row is None:
            return None
        return self._row_to_session(row)

    # ── Metrics snapshot operations ────────────────────────────────

    def insert_snapshot(self, snapshot: MetricsSnapshot) -> None:
        with self._lock:
            self._conn.execute(
                """INSERT INTO metrics_snapshots
                   (id, session_id, timestamp, viewer_count, chat_rate, platform)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (snapshot.id, snapshot.session_id, snapshot.timestamp,
                 snapshot.viewer_count, snapshot.chat_rate, snapshot.platform),
            )
            self._conn.commit()

    def query_snapshots(
        self, session_id: str, limit: int = 1000,
    ) -> list[MetricsSnapshot]:
        rows = self._conn.execute(
            "SELECT * FROM metrics_snapshots WHERE session_id = ? ORDER BY timestamp ASC LIMIT ?",
            (session_id, limit),
        ).fetchall()
        return [self._row_to_snapshot(r) for r in rows]

    # ── Event log operations ───────────────────────────────────────

    def insert_event(self, event: AnalyticsEvent) -> None:
        with self._lock:
            self._conn.execute(
                """INSERT INTO event_log
                   (id, session_id, timestamp, event_type, payload)
                   VALUES (?, ?, ?, ?, ?)""",
                (event.id, event.session_id, event.timestamp,
                 event.event_type, json.dumps(event.payload)),
            )
            self._conn.commit()

    def query_events(
        self, session_id: str, event_type: Optional[str] = None, limit: int = 500,
    ) -> list[AnalyticsEvent]:
        if event_type:
            rows = self._conn.execute(
                "SELECT * FROM event_log WHERE session_id = ? AND event_type = ? ORDER BY timestamp ASC LIMIT ?",
                (session_id, event_type, limit),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM event_log WHERE session_id = ? ORDER BY timestamp ASC LIMIT ?",
                (session_id, limit),
            ).fetchall()
        return [self._row_to_event(r) for r in rows]

    # ── Aggregation queries ────────────────────────────────────────

    def query_aggregates(self, session_id: str) -> dict:
        """Compute aggregate metrics from snapshots and event_log."""
        snap_row = self._conn.execute(
            """SELECT
                   COALESCE(MAX(viewer_count), 0) as peak_viewers,
                   COALESCE(AVG(viewer_count), 0) as avg_viewers,
                   COUNT(*) as snapshot_count
               FROM metrics_snapshots WHERE session_id = ?""",
            (session_id,),
        ).fetchone()

        chat_count = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM event_log WHERE session_id = ? AND event_type = 'audience.chat.message'",
            (session_id,),
        ).fetchone()["cnt"]

        unique_chatters = self._conn.execute(
            """SELECT COUNT(DISTINCT json_extract(payload, '$.user')) as cnt
               FROM event_log WHERE session_id = ? AND event_type = 'audience.chat.message'""",
            (session_id,),
        ).fetchone()["cnt"]

        top_chatters = self._conn.execute(
            """SELECT json_extract(payload, '$.user') as chatters, COUNT(*) as cnt
               FROM event_log WHERE session_id = ? AND event_type = 'audience.chat.message'
               GROUP BY chatters ORDER BY cnt DESC LIMIT 5""",
            (session_id,),
        ).fetchall()

        poll_count = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM event_log WHERE session_id = ? AND event_type LIKE 'audience.poll.%'",
            (session_id,),
        ).fetchone()["cnt"]

        asset_count = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM event_log WHERE session_id = ? AND event_type = 'media.asset.created'",
            (session_id,),
        ).fetchone()["cnt"]

        return {
            "peak_viewers": snap_row["peak_viewers"],
            "avg_viewers": round(snap_row["avg_viewers"], 1),
            "total_chat_messages": chat_count,
            "unique_chatters": unique_chatters,
            "snapshot_count": snap_row["snapshot_count"],
            "top_chatters": [
                {"user": r["chatters"], "count": r["cnt"]} for r in top_chatters
            ],
            "polls_conducted": poll_count,
            "assets_created": asset_count,
        }

    def get_dashboard_totals(self) -> dict:
        """Get aggregate totals across all ended sessions."""
        row = self._conn.execute(
            """SELECT
                   COUNT(*) as total_sessions,
                   COALESCE(SUM(total_chat_messages), 0) as total_messages,
                   COALESCE(SUM(duration_seconds), 0) as total_duration,
                   COALESCE(MAX(peak_viewers), 0) as all_time_peak
               FROM broadcast_sessions WHERE status = 'ended'"""
        ).fetchone()
        return {
            "total_sessions": row["total_sessions"],
            "total_messages": row["total_messages"],
            "total_duration_hours": round(row["total_duration"] / 3600, 1),
            "all_time_peak": row["all_time_peak"],
        }

    # ── Row deserialization helpers ────────────────────────────────

    @staticmethod
    def _row_to_session(row: sqlite3.Row) -> BroadcastSession:
        return BroadcastSession(
            id=row["id"],
            started_at=row["started_at"],
            ended_at=row["ended_at"],
            duration_seconds=row["duration_seconds"],
            peak_viewers=row["peak_viewers"],
            avg_viewers=row["avg_viewers"],
            total_chat_messages=row["total_chat_messages"],
            unique_chatters=row["unique_chatters"],
            platforms=json.loads(row["platforms"]),
            status=row["status"],
            created_at=row["created_at"],
        )

    @staticmethod
    def _row_to_snapshot(row: sqlite3.Row) -> MetricsSnapshot:
        return MetricsSnapshot(
            id=row["id"],
            session_id=row["session_id"],
            timestamp=row["timestamp"],
            viewer_count=row["viewer_count"],
            chat_rate=row["chat_rate"],
            platform=row["platform"],
        )

    @staticmethod
    def _row_to_event(row: sqlite3.Row) -> AnalyticsEvent:
        return AnalyticsEvent(
            id=row["id"],
            session_id=row["session_id"],
            timestamp=row["timestamp"],
            event_type=row["event_type"],
            payload=json.loads(row["payload"]),
        )

    def close(self) -> None:
        """Close the database connection."""
        if hasattr(self._local, "conn") and self._local.conn:
            self._local.conn.close()
            self._local.conn = None

"""Tests for the Analytics Suite — models, database, collector, session, reporting, and API."""

from __future__ import annotations

import json
from time import time

import pytest

from broadcast.analytics.database import AnalyticsDatabase
from broadcast.analytics.models import (
    AnalyticsEvent,
    AnalyticsReport,
    BroadcastSession,
    EngagementMetrics,
    MetricsSnapshot,
    ReportSummary,
)


# ── Model tests ────────────────────────────────────────────────────

class TestAnalyticsModels:
    def test_broadcast_session_defaults(self):
        s = BroadcastSession(id="s1", started_at=100.0)
        assert s.status == "live"
        assert s.platforms == []
        assert s.peak_viewers == 0

    def test_broadcast_session_ended(self):
        s = BroadcastSession(id="s1", started_at=100.0, ended_at=200.0, status="ended")
        assert s.status == "ended"
        assert s.ended_at == 200.0

    def test_metrics_snapshot_defaults(self):
        s = MetricsSnapshot(id="m1", session_id="s1", timestamp=100.0)
        assert s.viewer_count == 0
        assert s.chat_rate == 0.0
        assert s.platform == "all"

    def test_analytics_event_defaults(self):
        e = AnalyticsEvent(id="e1", session_id="s1", timestamp=100.0, event_type="test")
        assert e.payload == {}

    def test_analytics_report_roundtrip(self):
        report = AnalyticsReport(
            session_id="s1",
            summary=ReportSummary(duration_seconds=100.0, peak_viewers=50, avg_viewers=25.0, platforms=["twitch"], status="ended"),
            engagement=EngagementMetrics(total_chat_messages=200, unique_chatters=10, messages_per_minute=2.0),
        )
        data = report.model_dump()
        restored = AnalyticsReport(**data)
        assert restored.session_id == "s1"
        assert restored.summary.peak_viewers == 50
        assert restored.engagement.total_chat_messages == 200


# ── Database tests ─────────────────────────────────────────────────

@pytest.fixture
def db(tmp_path):
    """Create an AnalyticsDatabase backed by a temporary file."""
    db_path = tmp_path / "test_analytics.db"
    return AnalyticsDatabase(str(db_path))


class TestAnalyticsDatabase:
    def test_init_creates_tables(self, db):
        """Verify tables exist after init."""
        tables = db._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        names = [r["name"] for r in tables]
        assert "broadcast_sessions" in names
        assert "metrics_snapshots" in names
        assert "event_log" in names

    def test_insert_and_get_session(self, db):
        s = BroadcastSession(id="s1", started_at=100.0)
        db.insert_session(s)
        got = db.get_session("s1")
        assert got is not None
        assert got.id == "s1"
        assert got.started_at == 100.0

    def test_get_session_not_found(self, db):
        assert db.get_session("nonexistent") is None

    def test_update_session(self, db):
        s = BroadcastSession(id="s1", started_at=100.0)
        db.insert_session(s)
        s.status = "ended"
        s.peak_viewers = 42
        db.update_session(s)
        got = db.get_session("s1")
        assert got is not None
        assert got.status == "ended"
        assert got.peak_viewers == 42

    def test_list_sessions_ordered(self, db):
        for i in range(3):
            s = BroadcastSession(id=f"s{i}", started_at=float(i), created_at=float(i))
            db.insert_session(s)
        sessions = db.list_sessions(limit=10)
        assert len(sessions) >= 3
        # Most recent first
        assert sessions[0].created_at >= sessions[-1].created_at

    def test_list_sessions_filter_by_status(self, db):
        db.insert_session(BroadcastSession(id="live1", started_at=100.0, status="live"))
        db.insert_session(BroadcastSession(id="end1", started_at=50.0, status="ended", ended_at=80.0))
        live = db.list_sessions(status="live")
        ended = db.list_sessions(status="ended")
        assert all(s.status == "live" for s in live)
        assert all(s.status == "ended" for s in ended)

    def test_get_active_session(self, db):
        db.insert_session(BroadcastSession(id="s1", started_at=100.0, status="live"))
        db.insert_session(BroadcastSession(id="s2", started_at=50.0, status="ended", ended_at=80.0))
        active = db.get_active_session()
        assert active is not None
        assert active.id == "s1"

    def test_get_active_session_none(self, db):
        assert db.get_active_session() is None

    def test_insert_and_query_snapshots(self, db):
        db.insert_session(BroadcastSession(id="s1", started_at=100.0, status="live"))
        snap1 = MetricsSnapshot(id="m1", session_id="s1", timestamp=100.0, viewer_count=10)
        snap2 = MetricsSnapshot(id="m2", session_id="s1", timestamp=110.0, viewer_count=20)
        db.insert_snapshot(snap1)
        db.insert_snapshot(snap2)
        snaps = db.query_snapshots("s1")
        assert len(snaps) == 2
        assert snaps[0].viewer_count == 10

    def test_insert_and_query_events(self, db):
        db.insert_session(BroadcastSession(id="s1", started_at=100.0, status="live"))
        evt = AnalyticsEvent(id="e1", session_id="s1", timestamp=100.0, event_type="test.event")
        db.insert_event(evt)
        events = db.query_events("s1")
        assert len(events) == 1
        assert events[0].event_type == "test.event"

    def test_query_events_filter_by_type(self, db):
        db.insert_session(BroadcastSession(id="s1", started_at=100.0, status="live"))
        db.insert_event(AnalyticsEvent(id="e1", session_id="s1", timestamp=100.0, event_type="a"))
        db.insert_event(AnalyticsEvent(id="e2", session_id="s1", timestamp=110.0, event_type="b"))
        events = db.query_events("s1", event_type="a")
        assert len(events) == 1
        assert events[0].event_type == "a"

    def test_query_aggregates(self, db):
        db.insert_session(BroadcastSession(id="s1", started_at=100.0, status="ended"))
        db.insert_snapshot(MetricsSnapshot(id="m1", session_id="s1", timestamp=100.0, viewer_count=10))
        db.insert_snapshot(MetricsSnapshot(id="m2", session_id="s1", timestamp=110.0, viewer_count=30))
        db.insert_event(AnalyticsEvent(
            id="e1", session_id="s1", timestamp=100.0, event_type="audience.chat.message",
            payload={"user": "alice"},
        ))
        db.insert_event(AnalyticsEvent(
            id="e2", session_id="s1", timestamp=105.0, event_type="audience.chat.message",
            payload={"user": "bob"},
        ))
        agg = db.query_aggregates("s1")
        assert agg["peak_viewers"] == 30
        assert agg["avg_viewers"] == 20.0
        assert agg["total_chat_messages"] == 2

    def test_next_id_increments(self, db):
        id1 = db._next_id()
        id2 = db._next_id()
        assert id1 != id2
        assert id2.endswith("_2")

    def test_close(self, db):
        db.close()  # should not raise
        db.close()  # idempotent

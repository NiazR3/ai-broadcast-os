"""Tests for the Analytics Suite — models, database, collector, session, reporting, and API."""

from __future__ import annotations

import asyncio
import json
from time import time

import pytest

from broadcast.analytics.collector import MetricsCollector
from broadcast.analytics.reporting import ReportGenerator
from broadcast.analytics.database import AnalyticsDatabase
from broadcast.analytics.models import (
    AnalyticsEvent,
    AnalyticsReport,
    BroadcastSession,
    EngagementMetrics,
    MetricsSnapshot,
    ReportSummary,
)
from broadcast.analytics.session import SessionManager
from broadcast.events.bus import EventBus


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


# ── SessionManager tests ───────────────────────────────────────────

class TestSessionManager:
    def test_create_session(self, db):
        sm = SessionManager(db)
        s = sm.create_session(platforms=["twitch", "youtube"])
        assert s.status == "live"
        assert "twitch" in s.platforms
        assert s.id.startswith("sess_")

    def test_close_session_computes_aggregates(self, db):
        sm = SessionManager(db)
        s = sm.create_session()
        # Add some test data
        db.insert_snapshot(MetricsSnapshot(id="m1", session_id=s.id, timestamp=100.0, viewer_count=10))
        db.insert_snapshot(MetricsSnapshot(id="m2", session_id=s.id, timestamp=110.0, viewer_count=50))
        closed = sm.close_session(s.id)
        assert closed is not None
        assert closed.status == "ended"
        assert closed.peak_viewers == 50
        assert closed.avg_viewers == 30.0

    def test_close_session_not_found(self, db):
        sm = SessionManager(db)
        result = sm.close_session("nonexistent")
        assert result is None

    def test_close_session_already_ended(self, db):
        sm = SessionManager(db)
        s = sm.create_session()
        sm.close_session(s.id)
        s2 = sm.close_session(s.id)  # second close should not raise
        assert s2 is not None
        assert s2.status == "ended"

    def test_get_active_session(self, db):
        sm = SessionManager(db)
        assert sm.get_active_session() is None
        sm.create_session()
        assert sm.get_active_session() is not None

    def test_list_sessions(self, db):
        sm = SessionManager(db)
        s1 = sm.create_session()
        sm.close_session(s1.id)
        s2 = sm.create_session()
        sessions = sm.list_sessions()
        assert len(sessions) >= 2


# ── MetricsCollector tests ─────────────────────────────────────────

class TestMetricsCollector:
    def test_start_stop(self, db):
        bus = EventBus()
        sm = SessionManager(db)
        mc = MetricsCollector(db, bus, sm)
        
        async def _test():
            mc.start()
            assert mc.is_running
            mc.stop()
            assert not mc.is_running

        asyncio.run(_test())

    def test_broadcast_start_creates_session(self, db):
        bus = EventBus()
        sm = SessionManager(db)
        mc = MetricsCollector(db, bus, sm)

        async def _test():
            mc.start()
            await asyncio.sleep(0)  # Let _run() subscribe before publishing
            await bus.publish("broadcast", {"type": "broadcast.started", "platforms": ["twitch"]})
            await asyncio.sleep(0.1)
            mc.stop()

        asyncio.run(_test())

        active = sm.get_active_session()
        assert active is not None
        assert "twitch" in active.platforms

    def test_collector_logs_chat_events(self, db):
        bus = EventBus()
        sm = SessionManager(db)
        mc = MetricsCollector(db, bus, sm)

        # Create session synchronously
        s = sm.create_session()
        mc._current_session_id = s.id

        async def _test():
            mc.start()
            await asyncio.sleep(0)  # Let _run() subscribe before publishing
            await bus.publish("broadcast", {
                "type": "audience.chat.message", "user": "alice", "text": "hello", "timestamp": 100.0,
            })
            await asyncio.sleep(0.1)
            mc.stop()

        asyncio.run(_test())

        events = db.query_events(s.id)
        chat_events = [e for e in events if e.event_type == "audience.chat.message"]
        assert len(chat_events) > 0

    def test_collector_logs_scene_events(self, db):
        bus = EventBus()
        sm = SessionManager(db)
        mc = MetricsCollector(db, bus, sm)
        mc.start()

        s = sm.create_session()
        mc._current_session_id = s.id
        mc._log_event("scene.switched", {"scene": "Gameplay"})

        mc.stop()
        events = db.query_events(s.id, event_type="scene.switched")
        assert len(events) == 1
        assert events[0].payload.get("scene") == "Gameplay"

    def test_take_snapshot(self, db):
        bus = EventBus()
        sm = SessionManager(db)
        mc = MetricsCollector(db, bus, sm)
        mc.start()

        s = sm.create_session()
        mc._current_session_id = s.id
        mc._chat_count = 5
        mc._take_snapshot()

        mc.stop()
        snaps = db.query_snapshots(s.id)
        assert len(snaps) >= 1


# ── ReportGenerator tests ──────────────────────────────────────────

class TestReportGenerator:
    def test_build_report_returns_none_for_missing(self, db):
        rg = ReportGenerator(db)
        assert rg.build_report("nonexistent") is None

    def test_build_report_with_data(self, db):
        sm = SessionManager(db)
        s = sm.create_session(platforms=["twitch"])
        db.insert_snapshot(MetricsSnapshot(id="m1", session_id=s.id, timestamp=100.0, viewer_count=10))
        db.insert_snapshot(MetricsSnapshot(id="m2", session_id=s.id, timestamp=110.0, viewer_count=50))
        db.insert_event(AnalyticsEvent(
            id="e1", session_id=s.id, timestamp=100.0,
            event_type="audience.chat.message", payload={"user": "alice"},
        ))
        sm.close_session(s.id)

        rg = ReportGenerator(db)
        report = rg.build_report(s.id)
        assert report is not None
        assert report.session_id == s.id
        assert report.summary.peak_viewers == 50
        assert report.summary.avg_viewers == 30.0
        assert report.engagement.total_chat_messages == 1
        assert len(report.timeline) >= 1

    def test_build_csv(self, db):
        from broadcast.analytics.session import SessionManager
        from broadcast.analytics.reporting import ReportGenerator
        import csv, io
        sm = SessionManager(db)
        s = sm.create_session()
        db.insert_snapshot(MetricsSnapshot(id="m1", session_id=s.id, timestamp=100.0, viewer_count=10))
        db.insert_snapshot(MetricsSnapshot(id="m2", session_id=s.id, timestamp=110.0, viewer_count=20))

        rg = ReportGenerator(db)
        csv_str = rg.build_csv(s.id)
        assert csv_str is not None
        reader = csv.reader(io.StringIO(csv_str))
        rows = list(reader)
        assert rows[0] == ["timestamp", "viewer_count", "chat_rate", "platform"]
        assert rows[1][1] == "10"  # viewer_count cell
        assert rows[2][1] == "20"  # viewer_count cell

    def test_build_csv_no_data(self, db):
        rg = ReportGenerator(db)
        assert rg.build_csv("nonexistent") is None

    def test_build_report_zero_chat_events(self, db):
        """Report with no chat events should have 0 messages_per_minute."""
        sm = SessionManager(db)
        s = sm.create_session()
        db.insert_snapshot(MetricsSnapshot(id="m1", session_id=s.id, timestamp=100.0, viewer_count=10))
        sm.close_session(s.id)
        rg = ReportGenerator(db)
        report = rg.build_report(s.id)
        assert report is not None
        assert report.engagement.total_chat_messages == 0
        assert report.engagement.messages_per_minute == 0.0

    def test_build_report_zero_duration(self, db):
        """Session with 0 duration should handle division safely."""
        import time as ttime
        sm = SessionManager(db)
        s = BroadcastSession(id=db._next_id("sess"), started_at=ttime.time(), status="live", created_at=ttime.time())
        db.insert_session(s)
        db.insert_snapshot(MetricsSnapshot(id="m1", session_id=s.id, timestamp=ttime.time(), viewer_count=5))
        # Immediately close
        sm.close_session(s.id)
        rg = ReportGenerator(db)
        report = rg.build_report(s.id)
        assert report is not None
        assert report.summary.duration_seconds >= 0
        assert report.engagement.messages_per_minute == 0.0

    def test_build_dashboard_no_data(self, db):
        rg = ReportGenerator(db)
        dash = rg.build_dashboard()
        assert dash["live_session"] is None
        assert dash["totals"]["total_sessions"] == 0

    def test_build_dashboard_with_data(self, db):
        sm = SessionManager(db)
        s = sm.create_session(platforms=["twitch"])
        sm.close_session(s.id)

        rg = ReportGenerator(db)
        dash = rg.build_dashboard()
        assert dash["live_session"] is None  # closed
        assert len(dash["recent_sessions"]) >= 1
        assert dash["totals"]["total_sessions"] == 1


# ── API endpoint tests ─────────────────────────────────────────────

_HEADERS = {"X-API-Key": "test-key"}


class TestAnalyticsAPI:
    @pytest.fixture(autouse=True)
    def _reset_analytics(self, tmp_path):
        """Replace module-level agent with a temp-db version for test isolation."""
        from broadcast.analytics.agent import AnalyticsAgent
        from broadcast.analytics.router import _replace_agent

        db_path = str(tmp_path / "test_analytics_api.db")
        test_agent = AnalyticsAgent(db_path=db_path)
        test_agent.start()
        _replace_agent(test_agent)
        yield
        test_agent.stop()

    def test_list_sessions_empty(self, client):
        resp = client.get("/api/analytics/sessions", headers=_HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    def test_get_session_not_found(self, client):
        resp = client.get("/api/analytics/sessions/nonexistent", headers=_HEADERS)
        assert resp.status_code == 404

    def test_live_metrics_no_session(self, client):
        resp = client.get("/api/analytics/live", headers=_HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert data["live"] is False

    def test_dashboard_empty(self, client):
        resp = client.get("/api/analytics/dashboard", headers=_HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert data["live_session"] is None

    def test_create_and_get_report(self, client):
        from broadcast.analytics.router import _agent as analytics_agent
        from broadcast.analytics.models import MetricsSnapshot, AnalyticsEvent
        from broadcast.analytics.session import SessionManager

        sm = SessionManager(analytics_agent.db)
        s = sm.create_session(platforms=["twitch"])
        analytics_agent.db.insert_snapshot(MetricsSnapshot(
            id=analytics_agent.db._next_id("m"), session_id=s.id,
            timestamp=100.0, viewer_count=10,
        ))
        analytics_agent.db.insert_snapshot(MetricsSnapshot(
            id=analytics_agent.db._next_id("m"), session_id=s.id,
            timestamp=110.0, viewer_count=50,
        ))
        analytics_agent.db.insert_event(AnalyticsEvent(
            id=analytics_agent.db._next_id("e"), session_id=s.id,
            timestamp=100.0, event_type="audience.chat.message",
            payload={"user": "alice"},
        ))
        sm.close_session(s.id)

        resp = client.get(f"/api/analytics/sessions/{s.id}/report", headers=_HEADERS)
        assert resp.status_code == 200
        report = resp.json()
        assert report["session_id"] == s.id
        assert report["summary"]["peak_viewers"] == 50

    def test_csv_endpoint(self, client):
        from broadcast.analytics.router import _agent as analytics_agent
        from broadcast.analytics.models import MetricsSnapshot
        from broadcast.analytics.session import SessionManager

        sm = SessionManager(analytics_agent.db)
        s = sm.create_session()
        analytics_agent.db.insert_snapshot(MetricsSnapshot(
            id=analytics_agent.db._next_id("m"), session_id=s.id,
            timestamp=100.0, viewer_count=10,
        ))

        resp = client.get(f"/api/analytics/sessions/{s.id}/report.csv", headers=_HEADERS)
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/csv")
        assert "viewer_count" in resp.text


# ── Integration test ───────────────────────────────────────────────

class TestAnalyticsIntegration:
    """End-to-end: simulate broadcast lifecycle → metrics collected → report generated."""

    def test_full_lifecycle(self, db):
        """Simulate a complete broadcast session through EventBus."""
        bus = EventBus()
        sm = SessionManager(db)
        mc = MetricsCollector(db, bus, sm)
        mc.start()

        # 1. Broadcast starts
        s = sm.create_session(platforms=["twitch", "youtube"])
        mc._current_session_id = s.id

        # 2. Simulate events during broadcast
        mc._on_chat_event({"type": "audience.chat.message", "user": "alice", "text": "hello!", "timestamp": 100.0})
        mc._on_chat_event({"type": "audience.chat.message", "user": "bob", "text": "hi", "timestamp": 101.0})
        mc._on_chat_event({"type": "audience.chat.message", "user": "alice", "text": "great stream", "timestamp": 102.0})
        mc._log_event("scene.switched", {"scene": "Intro"})
        mc._log_event("scene.switched", {"scene": "Gameplay"})
        mc._log_event("audience.poll.created", {"poll_id": "poll1", "question": "Best game?"})

        # 3. Take snapshots
        db.insert_snapshot(MetricsSnapshot(id="m1", session_id=s.id, timestamp=100.0, viewer_count=10))
        db.insert_snapshot(MetricsSnapshot(id="m2", session_id=s.id, timestamp=110.0, viewer_count=50))
        db.insert_snapshot(MetricsSnapshot(id="m3", session_id=s.id, timestamp=120.0, viewer_count=30))

        # 4. Broadcast ends
        sm.close_session(s.id)
        mc.stop()

        # 5. Verify session data
        session = db.get_session(s.id)
        assert session is not None
        assert session.status == "ended"
        assert session.peak_viewers == 50
        assert session.avg_viewers == 30.0
        assert session.total_chat_messages == 3

        # 6. Verify timeline events
        events = db.query_events(s.id)
        event_types = [e.event_type for e in events]
        assert "audience.chat.message" in event_types
        assert "scene.switched" in event_types
        assert "audience.poll.created" in event_types

        # 7. Generate and verify report
        rg = ReportGenerator(db)
        report = rg.build_report(s.id)
        assert report is not None
        assert report.summary.peak_viewers == 50
        assert report.engagement.total_chat_messages == 3
        assert report.engagement.unique_chatters == 2
        assert len([e for e in report.timeline if e.event_type == "scene.switched"]) == 2

        # 8. Verify CSV
        csv_str = rg.build_csv(s.id)
        assert csv_str is not None

        # 9. Verify dashboard data
        dash = rg.build_dashboard()
        assert dash["live_session"] is None
        assert len(dash["recent_sessions"]) >= 1

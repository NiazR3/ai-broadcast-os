"""Post-stream report generation — JSON reports and CSV exports."""

from __future__ import annotations

import csv
import io
import logging
from time import time
from typing import Optional

from broadcast.analytics.database import AnalyticsDatabase
from broadcast.analytics.models import (
    AnalyticsEvent,
    AnalyticsReport,
    EngagementMetrics,
    ReportSummary,
)

logger = logging.getLogger(__name__)


class ReportGenerator:
    """Generates post-stream reports from analytics data."""

    def __init__(self, db: AnalyticsDatabase) -> None:
        self._db = db

    def build_report(self, session_id: str) -> Optional[AnalyticsReport]:
        """Build a complete post-stream report for a session."""
        session = self._db.get_session(session_id)
        if session is None:
            return None

        agg = self._db.query_aggregates(session_id)
        events = self._db.query_events(session_id)

        summary = ReportSummary(
            duration_seconds=session.duration_seconds,
            peak_viewers=agg["peak_viewers"],
            avg_viewers=agg["avg_viewers"],
            platforms=session.platforms,
            status=session.status,
        )

        chat_events = [e for e in events if e.event_type == "audience.chat.message"]
        mpm = 0.0
        if session.duration_seconds > 0:
            mpm = round(len(chat_events) / (session.duration_seconds / 60), 1)

        engagement = EngagementMetrics(
            total_chat_messages=agg["total_chat_messages"],
            unique_chatters=agg["unique_chatters"],
            messages_per_minute=mpm,
            top_chatters=agg["top_chatters"],
            polls_conducted=agg["polls_conducted"],
            assets_created=agg["assets_created"],
        )

        report = AnalyticsReport(
            session_id=session_id,
            summary=summary,
            engagement=engagement,
            timeline=events,
            generated_at=time(),
        )
        return report

    def build_csv(self, session_id: str) -> Optional[str]:
        """Build a CSV string of metrics snapshots for a session."""
        snapshots = self._db.query_snapshots(session_id)
        if not snapshots:
            return None

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["timestamp", "viewer_count", "chat_rate", "platform"])
        for snap in snapshots:
            writer.writerow([
                f"{snap.timestamp:.1f}",
                snap.viewer_count,
                f"{snap.chat_rate:.1f}",
                snap.platform,
            ])
        return output.getvalue()

    def build_dashboard(self) -> dict:
        """Build aggregated data for the dashboard overview.

        Returns:
            dict with keys: live_session, recent_sessions, totals
        """
        active = self._db.get_active_session()
        recent = self._db.list_sessions(limit=5)

        return {
            "live_session": active.model_dump() if active else None,
            "recent_sessions": [s.model_dump() for s in recent],
            "totals": self._db.get_dashboard_totals(),
        }

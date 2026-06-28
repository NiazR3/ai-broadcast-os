"""Analytics REST API endpoints — sessions, metrics, reports, and dashboard data."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse

from broadcast.analytics.agent import AnalyticsAgent
from broadcast.auth import verify_api_key

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analytics", tags=["analytics"], dependencies=[Depends(verify_api_key)])

# Module-level singleton
_agent = AnalyticsAgent()
_agent.start()


def _replace_agent(agent: AnalyticsAgent) -> None:
    """Replace the module-level agent (used for test injection)."""
    global _agent
    _agent.stop()
    _agent = agent


@router.get("/sessions")
def list_sessions(
    limit: int = Query(default=20, ge=1, le=100),
    status: Optional[str] = None,
) -> list[dict]:
    """List broadcast sessions."""
    return [s.model_dump() for s in _agent.session_manager.list_sessions(limit=limit, status=status)]


@router.get("/sessions/{session_id}")
def get_session(session_id: str) -> dict:
    """Get a single broadcast session."""
    session = _agent.session_manager.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return session.model_dump()


@router.get("/sessions/{session_id}/report")
def get_session_report(session_id: str) -> dict:
    """Get post-stream analytics report."""
    report = _agent.report_generator.build_report(session_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return report.model_dump()


@router.get("/sessions/{session_id}/report.csv", response_class=PlainTextResponse)
def get_session_report_csv(session_id: str) -> str:
    """Download metrics snapshots as CSV."""
    csv_str = _agent.report_generator.build_csv(session_id)
    if csv_str is None:
        raise HTTPException(status_code=404, detail="Session not found or no metrics data")
    return PlainTextResponse(
        content=csv_str,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=session_{session_id}_metrics.csv"},
    )


@router.get("/live")
def get_live_metrics() -> dict:
    """Get current live session metrics."""
    session = _agent.session_manager.get_active_session()
    if session is None:
        return {"live": False, "session": None}
    return {
        "live": True,
        "session": session.model_dump(),
    }


@router.get("/dashboard")
def get_dashboard_data() -> dict:
    """Get aggregated dashboard overview data."""
    return _agent.report_generator.build_dashboard()

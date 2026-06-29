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

# Module-level singleton — defer start() to FastAPI lifespan so there's an event loop
_agent: Optional[AnalyticsAgent] = None


def get_agent() -> AnalyticsAgent:
    """Get or create the singleton analytics agent."""
    global _agent
    if _agent is None:
        _agent = AnalyticsAgent()
    return _agent


def start_agent() -> None:
    """Start the analytics agent (call from FastAPI lifespan startup)."""
    agent = get_agent()
    agent.start()


def stop_agent() -> None:
    """Stop the analytics agent (call from FastAPI lifespan shutdown)."""
    global _agent
    if _agent is not None:
        _agent.stop()
        _agent = None


def _replace_agent(agent: AnalyticsAgent) -> None:
    """Replace the module-level agent (used for test injection)."""
    global _agent
    if _agent is not None:
        _agent.stop()
    _agent = agent


@router.get("/sessions")
def list_sessions(
    limit: int = Query(default=20, ge=1, le=100),
    status: Optional[str] = None,
) -> list[dict]:
    """List broadcast sessions."""
    return [s.model_dump() for s in get_agent().session_manager.list_sessions(limit=limit, status=status)]


@router.get("/sessions/{session_id}")
def get_session(session_id: str) -> dict:
    """Get a single broadcast session."""
    session = get_agent().session_manager.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return session.model_dump()


@router.get("/sessions/{session_id}/report")
def get_session_report(session_id: str) -> dict:
    """Get post-stream analytics report."""
    report = get_agent().report_generator.build_report(session_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return report.model_dump()


@router.get("/sessions/{session_id}/report.csv", response_class=PlainTextResponse)
def get_session_report_csv(session_id: str) -> str:
    """Download metrics snapshots as CSV."""
    csv_str = get_agent().report_generator.build_csv(session_id)
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
    session = get_agent().session_manager.get_active_session()
    if session is None:
        return {"live": False, "session": None}
    return {
        "live": True,
        "session": session.model_dump(),
    }


@router.get("/dashboard")
def get_dashboard_data() -> dict:
    """Get aggregated dashboard overview data."""
    return get_agent().report_generator.build_dashboard()

"""Pydantic models for analytics — sessions, metrics, events, and reports."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class BroadcastSession(BaseModel):
    """A single broadcast session with aggregated metrics."""
    id: str = Field(..., min_length=1)
    started_at: float = 0.0
    ended_at: Optional[float] = None
    duration_seconds: float = 0.0
    peak_viewers: int = 0
    avg_viewers: float = 0.0
    total_chat_messages: int = 0
    unique_chatters: int = 0
    platforms: list[str] = Field(default_factory=list)
    status: str = "live"  # "live" | "ended"
    created_at: float = 0.0


class MetricsSnapshot(BaseModel):
    """Time-series metrics data point."""
    id: str = Field(..., min_length=1)
    session_id: str = Field(..., min_length=1)
    timestamp: float = 0.0
    viewer_count: int = 0
    chat_rate: float = 0.0  # messages/min in the last window
    platform: str = "all"


class AnalyticsEvent(BaseModel):
    """A structured event that occurred during a broadcast."""
    id: str = Field(..., min_length=1)
    session_id: str = Field(..., min_length=1)
    timestamp: float = 0.0
    event_type: str = Field(..., min_length=1)
    payload: dict = Field(default_factory=dict)


class ReportSummary(BaseModel):
    """High-level session summary for post-stream reports."""
    duration_seconds: float = 0.0
    peak_viewers: int = 0
    avg_viewers: float = 0.0
    platforms: list[str] = Field(default_factory=list)
    status: str = "ended"


class EngagementMetrics(BaseModel):
    """Engagement statistics for post-stream reports."""
    total_chat_messages: int = 0
    unique_chatters: int = 0
    messages_per_minute: float = 0.0
    top_chatters: list[dict] = Field(default_factory=list)
    polls_conducted: int = 0
    assets_created: int = 0


class AnalyticsReport(BaseModel):
    """Complete post-stream analytics report."""
    session_id: str = Field(..., min_length=1)
    summary: ReportSummary = Field(default_factory=ReportSummary)
    engagement: EngagementMetrics = Field(default_factory=EngagementMetrics)
    timeline: list[AnalyticsEvent] = Field(default_factory=list)
    generated_at: float = 0.0

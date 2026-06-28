"""Data models for the Research Agent."""

from __future__ import annotations

from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field


class ResearchStatus(str, Enum):
    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    COMPLETE = "complete"
    FAILED = "failed"


class ResearchTopic(BaseModel):
    id: str = Field(min_length=1)
    query: str
    segment_id: str = ""
    segment_title: str = ""
    context: str = ""
    status: ResearchStatus = ResearchStatus.QUEUED
    created_at: float = 0.0
    completed_at: Optional[float] = None


class SourceCitation(BaseModel):
    url: str
    title: str
    snippet: str
    relevance_score: float = 0.0


class FactCheck(BaseModel):
    claim: str
    verdict: Literal["supported", "contradicted", "unverified"]
    explanation: str = ""


class ResearchResult(BaseModel):
    id: str
    topic_id: str
    summary: str
    key_points: list[str]
    sources: list[SourceCitation]
    fact_checks: list[FactCheck]
    created_at: float = 0.0

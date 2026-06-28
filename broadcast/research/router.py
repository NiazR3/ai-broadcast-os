"""Research REST API endpoints — submit topics, list results, extract topics."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from broadcast.auth import verify_api_key
from broadcast.research.engine import ResearchAgent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/research", tags=["research"], dependencies=[Depends(verify_api_key)])

# Module-level singleton
_agent = ResearchAgent()


@router.post("/submit")
def submit_research(body: dict) -> dict:
    """Submit a topic for research."""
    query = body.get("query", "").strip()
    if not query:
        raise HTTPException(status_code=422, detail="Research query is required")
    segment_id = body.get("segment_id", "")
    segment_title = body.get("segment_title", "")
    context = body.get("context", "")
    result = _agent.submit_research(query, segment_id, segment_title, context)
    return result


@router.get("/results")
def list_results(limit: int = Query(default=10, ge=1, le=50)) -> list[dict]:
    """List past research results."""
    return [r.model_dump() for r in _agent.list_results(limit)]


@router.get("/results/{result_id}")
def get_result(result_id: str) -> dict:
    """Get a specific research result."""
    result = _agent.get_result(result_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Result not found")
    return result.model_dump()


@router.post("/extract")
def extract_topics(body: dict) -> dict:
    """Extract research topics from text."""
    text = body.get("text", "").strip()
    if not text:
        raise HTTPException(status_code=422, detail="Text is required")
    topics = _agent.extract_topics(text)
    return {"topics": topics, "text": text}

"""Audience interaction REST API endpoints — chat, moderation, polls, and stats."""

from __future__ import annotations

import asyncio
import logging
from time import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from broadcast.audience.agent import AudienceAgent
from broadcast.audience.models import (
    ChatMessage, ChatPlatform, ChatUser, ChatUserRole,
    ModerationAction, ModerationRule, Poll,
)
from broadcast.auth import verify_api_key

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/audience", tags=["audience"], dependencies=[Depends(verify_api_key)])

# Module-level singleton
_agent = AudienceAgent()


# ── Chat endpoints ────────────────────────────────────────────────────

@router.get("/chat")
def list_chat(
    limit: int = Query(default=50, ge=1, le=200),
    user_id: Optional[str] = None,
    flagged: bool = False,
) -> list[dict]:
    """Get recent chat messages."""
    if flagged:
        msgs = _agent.get_flagged_messages()
    elif user_id:
        msgs = _agent.chat_repo.by_user(user_id)
    else:
        msgs = _agent.chat_repo.recent(limit)
    return [m.model_dump() for m in msgs]


@router.post("/chat")
def inject_chat(body: dict) -> dict:
    """Inject a chat message (for testing)."""
    platform_str = body.get("platform", "mock")
    if platform_str not in (p.value for p in ChatPlatform):
        raise HTTPException(status_code=422, detail=f"Invalid platform: {platform_str}")
    text = body.get("text", "").strip()
    if not text:
        raise HTTPException(status_code=422, detail="Message text is required")
    user_name = body.get("user_name", "TestUser")
    msg = ChatMessage(
        id=f"injected_{int(time() * 1000)}",
        platform=ChatPlatform(platform_str),
        user=ChatUser(
            id=body.get("user_id", user_name.lower()),
            display_name=user_name,
            platform=ChatPlatform(platform_str),
            role=ChatUserRole.VIEWER,
        ),
        text=text,
        timestamp=time(),
    )
    _agent.ingest_message(msg)
    return msg.model_dump()


@router.post("/chat/{message_id}/flag")
def flag_message(message_id: str) -> dict:
    """Flag a chat message for moderation review."""
    success = _agent.chat_repo.update_moderation(message_id, ModerationAction.FLAG.value)
    if not success:
        raise HTTPException(status_code=404, detail="Message not found")
    # Publish flag event (sync endpoint — use asyncio.run)
    asyncio.run(_agent._event_bus.publish("audience.moderation", {
        "type": "audience.moderation.flagged",
        "message_id": message_id,
        "timestamp": time(),
    }))
    return {"flagged": True, "message_id": message_id}


@router.post("/chat/{message_id}/moderate")
def moderate_message(message_id: str, body: dict) -> dict:
    """Apply a moderation action (approve/timeout/ban) to a flagged message."""
    action_str = body.get("action", "approve")
    if action_str not in (a.value for a in ModerationAction):
        raise HTTPException(status_code=422, detail=f"Invalid action: {action_str}")
    success = _agent.chat_repo.update_moderation(message_id, action_str)
    if not success:
        raise HTTPException(status_code=404, detail="Message not found")
    return {"moderated": True, "message_id": message_id, "action": action_str}


# ── Moderation rules endpoints ────────────────────────────────────────

@router.get("/moderation/rules")
def list_moderation_rules() -> list[dict]:
    """List all moderation rules."""
    return [r.model_dump() for r in _agent.moderation.list_rules()]


@router.post("/moderation/rules")
def create_moderation_rule(body: dict) -> dict:
    """Create a moderation rule."""
    pattern = body.get("pattern", "").strip()
    if not pattern:
        raise HTTPException(status_code=422, detail="Pattern is required")
    action_str = body.get("action", "flag")
    if action_str not in (a.value for a in ModerationAction):
        raise HTTPException(status_code=422, detail=f"Invalid action: {action_str}")
    rule = ModerationRule(
        id=f"rule_{int(time())}",
        pattern=pattern,
        action=ModerationAction(action_str),
        reason=body.get("reason", ""),
        created_at=time(),
    )
    _agent.moderation.add_rule(rule)
    return rule.model_dump()


@router.delete("/moderation/rules/{rule_id}")
def delete_moderation_rule(rule_id: str) -> dict:
    """Delete a moderation rule."""
    if not _agent.moderation.remove_rule(rule_id):
        raise HTTPException(status_code=404, detail="Rule not found")
    return {"deleted": True, "rule_id": rule_id}


# ── Poll endpoints ────────────────────────────────────────────────────

@router.get("/polls")
def list_polls(include_closed: bool = False) -> list[dict]:
    """List polls."""
    return [p.model_dump() for p in _agent.polls.list_polls(include_closed=include_closed)]


@router.post("/polls")
def create_poll(body: dict) -> dict:
    """Create a new poll."""
    question = body.get("question", "").strip()
    if not question:
        raise HTTPException(status_code=422, detail="Poll question is required")
    options = body.get("options", [])
    if len(options) < 2:
        raise HTTPException(status_code=422, detail="At least 2 options required")
    duration = body.get("duration_seconds", 60)
    poll = _agent.polls.create_poll(question, options, duration)
    return poll.model_dump()


@router.post("/polls/{poll_id}/vote")
def vote_poll(poll_id: str, body: dict) -> dict:
    """Vote on a poll."""
    option_index = body.get("option_index", -1)
    user_id = body.get("user_id", "").strip()
    if not user_id:
        raise HTTPException(status_code=422, detail="user_id is required")
    try:
        vote = _agent.polls.vote(poll_id, option_index, user_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return vote.model_dump()


@router.post("/polls/{poll_id}/close")
def close_poll(poll_id: str) -> dict:
    """Force-close a poll."""
    try:
        poll = _agent.polls.close_poll(poll_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return poll.model_dump()


# ── Stats endpoint ────────────────────────────────────────────────────

@router.get("/stats")
def get_audience_stats() -> dict:
    """Get aggregated audience activity stats."""
    return _agent.get_activity_summary().model_dump()


# ── Simulation control (convenience for dashboard) ────────────────────

@router.post("/simulation/start")
async def start_simulation(rate: float = Query(default=0.33, ge=0.1, le=10.0)) -> dict:
    """Start mock chat simulation."""
    await _agent.start_simulation(rate=rate)
    return {"running": True, "rate": rate}


@router.post("/simulation/stop")
async def stop_simulation() -> dict:
    """Stop mock chat simulation."""
    _agent.stop_simulation()
    return {"running": False}

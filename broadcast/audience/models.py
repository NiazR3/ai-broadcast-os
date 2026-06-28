"""Pydantic models for audience interaction, chat, moderation, and polls."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ChatPlatform(str, Enum):
    """Supported chat platforms."""
    TWITCH = "twitch"
    YOUTUBE = "youtube"
    FACEBOOK = "facebook"
    MOCK = "mock"


class ChatUserRole(str, Enum):
    """User roles within a chat platform."""
    VIEWER = "viewer"
    MODERATOR = "moderator"
    BROADCASTER = "broadcaster"
    VIP = "vip"


class ChatUser(BaseModel):
    """A chat user from any platform."""
    id: str = Field(..., min_length=1, description="Platform user ID")
    display_name: str = Field(..., min_length=1, description="Display name")
    platform: ChatPlatform = Field(..., description="Origin platform")
    role: ChatUserRole = ChatUserRole.VIEWER
    badges: list[str] = Field(default_factory=list)


class ChatMessage(BaseModel):
    """A single chat message."""
    id: str = Field(..., min_length=1, description="Unique message ID")
    platform: ChatPlatform = Field(..., description="Origin platform")
    user: ChatUser = Field(..., description="Sender")
    text: str = Field(..., min_length=1, description="Message content")
    timestamp: float = Field(default=0.0, description="Unix timestamp")
    moderated: bool = False
    moderation_action: Optional[str] = None


class ModerationAction(str, Enum):
    """Actions the moderation engine can take."""
    FLAG = "flag"
    APPROVE = "approve"
    TIMEOUT = "timeout"
    BAN = "ban"


class ModerationRule(BaseModel):
    """A single moderation rule (keyword or heuristic)."""
    id: str = Field(..., min_length=1)
    pattern: str = Field(..., min_length=1, description="Regex pattern")
    action: ModerationAction = ModerationAction.FLAG
    reason: str = Field(default="", description="Why this rule exists")
    enabled: bool = True
    created_at: float = 0.0


class PollStatus(str, Enum):
    """Lifecycle status of a poll."""
    PENDING = "pending"
    ACTIVE = "active"
    CLOSED = "closed"


class PollOption(BaseModel):
    """A single poll option with vote count."""
    text: str = Field(..., min_length=1)
    votes: int = 0


class Poll(BaseModel):
    """A poll question with multiple options."""
    id: str = Field(..., min_length=1)
    question: str = Field(..., min_length=1)
    options: list[PollOption] = Field(..., min_length=2, max_length=10)
    status: PollStatus = PollStatus.PENDING
    duration_seconds: int = Field(default=60, ge=10, le=600)
    created_at: float = 0.0
    closed_at: Optional[float] = None


class PollVote(BaseModel):
    """A single vote on a poll."""
    poll_id: str = Field(..., min_length=1)
    option_index: int = Field(..., ge=0)
    user_id: str = Field(..., min_length=1)
    timestamp: float = 0.0


class ChatActivity(BaseModel):
    """Aggregated chat statistics."""
    total_messages: int = 0
    unique_users: int = 0
    messages_per_minute: float = 0.0
    top_chatters: list[dict] = Field(default_factory=list)

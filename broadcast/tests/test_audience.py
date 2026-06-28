"""Tests for M4 — audience interaction & moderation."""

from __future__ import annotations

from time import time

import pytest
from pydantic import ValidationError

from broadcast.audience.models import (
    ChatMessage, ChatPlatform, ChatUser, ChatUserRole,
    ModerationAction, ModerationRule, Poll, PollOption,
    PollStatus, PollVote, ChatActivity,
)
from broadcast.audience.chat import ChatRepository


# ── Model tests ────────────────────────────────────────────────────────

class TestChatMessageModel:
    def test_minimal_chat_message(self):
        msg = ChatMessage(
            id="msg_1", platform=ChatPlatform.TWITCH,
            user=ChatUser(id="u1", display_name="Viewer1", platform=ChatPlatform.TWITCH),
            text="Hello!", timestamp=1000.0,
        )
        assert msg.id == "msg_1"
        assert msg.user.display_name == "Viewer1"
        assert msg.moderated is False

    def test_chat_message_empty_text_fails(self):
        with pytest.raises(ValidationError):
            ChatMessage(
                id="msg_2", platform=ChatPlatform.MOCK,
                user=ChatUser(id="u2", display_name="B", platform=ChatPlatform.MOCK),
                text="", timestamp=1.0,
            )

    def test_chat_message_defaults(self):
        msg = ChatMessage(
            id="m1", platform=ChatPlatform.MOCK,
            user=ChatUser(id="u1", display_name="U", platform=ChatPlatform.MOCK),
            text="Hi", timestamp=1.0,
        )
        assert msg.moderated is False
        assert msg.moderation_action is None


class TestModerationRuleModel:
    def test_minimal_rule(self):
        rule = ModerationRule(id="r1", pattern="badword", action=ModerationAction.FLAG, reason="Profanity")
        assert rule.enabled is True
        assert rule.created_at == 0.0

    def test_rule_empty_pattern_fails(self):
        with pytest.raises(ValidationError):
            ModerationRule(id="r2", pattern="", action=ModerationAction.BAN, reason="Empty")


class TestPollModel:
    def test_minimal_poll(self):
        poll = Poll(id="p1", question="Favorite color?", options=[
            PollOption(text="Red"), PollOption(text="Blue"),
        ])
        assert poll.status == PollStatus.PENDING
        assert len(poll.options) == 2
        assert poll.options[0].votes == 0

    def test_poll_requires_at_least_two_options(self):
        with pytest.raises(ValidationError):
            Poll(id="p2", question="Test?", options=[PollOption(text="Only")])

    def test_poll_up_to_ten_options(self):
        options = [PollOption(text=f"Option {i}") for i in range(10)]
        poll = Poll(id="p3", question="Many?", options=options)
        assert len(poll.options) == 10

    def test_poll_eleven_options_fails(self):
        with pytest.raises(ValidationError):
            Poll(id="p4", question="Too many?", options=[PollOption(text=f"O{i}") for i in range(11)])


class TestPollVoteModel:
    def test_vote_fields(self):
        vote = PollVote(poll_id="p1", option_index=1, user_id="u1", timestamp=100.0)
        assert vote.poll_id == "p1"
        assert vote.option_index == 1
        assert vote.user_id == "u1"

    def test_vote_negative_index_fails(self):
        with pytest.raises(ValidationError):
            PollVote(poll_id="p1", option_index=-1, user_id="u1", timestamp=1.0)


class TestChatActivityModel:
    def test_defaults(self):
        ca = ChatActivity()
        assert ca.total_messages == 0
        assert ca.unique_users == 0
        assert ca.messages_per_minute == 0.0

    def test_with_values(self):
        ca = ChatActivity(total_messages=50, unique_users=10, messages_per_minute=5.0, top_chatters=[{"user": "u1", "count": 20}])
        assert ca.total_messages == 50


# ── ChatRepository tests ───────────────────────────────────────────────

class TestChatRepository:
    def test_add_and_recent(self):
        repo = ChatRepository()
        msg = ChatMessage(
            id="m1", platform=ChatPlatform.MOCK,
            user=ChatUser(id="u1", display_name="U1", platform=ChatPlatform.MOCK),
            text="Hello", timestamp=1.0,
        )
        repo.add(msg)
        recent = repo.recent()
        assert len(recent) == 1
        assert recent[0].text == "Hello"

    def test_recent_returns_newest_first_in_reverse_order(self):
        repo = ChatRepository()
        for i in range(5):
            msg = ChatMessage(
                id=f"m{i}", platform=ChatPlatform.MOCK,
                user=ChatUser(id="u1", display_name="U1", platform=ChatPlatform.MOCK),
                text=f"Msg {i}", timestamp=float(i),
            )
            repo.add(msg)
        recent = repo.recent(3)
        assert len(recent) == 3
        # order should be newest first
        texts = [m.text for m in recent]
        assert texts == ["Msg 4", "Msg 3", "Msg 2"]

    def test_by_user(self):
        repo = ChatRepository()
        for i in range(3):
            repo.add(ChatMessage(
                id=f"m{i}", platform=ChatPlatform.MOCK,
                user=ChatUser(id="u1", display_name="U1", platform=ChatPlatform.MOCK),
                text=f"Hi {i}", timestamp=float(i),
            ))
        repo.add(ChatMessage(
            id="m_other", platform=ChatPlatform.MOCK,
            user=ChatUser(id="u2", display_name="U2", platform=ChatPlatform.MOCK),
            text="Other", timestamp=5.0,
        ))
        u1_msgs = repo.by_user("u1")
        assert len(u1_msgs) == 3

    def test_ring_buffer_evicts_oldest(self):
        repo = ChatRepository()
        # Force a small cap by testing eviction logic directly
        # Add MAX_MESSAGES + 1 messages
        for i in range(501):
            msg = ChatMessage(
                id=f"m{i:04d}", platform=ChatPlatform.MOCK,
                user=ChatUser(id="u1", display_name="U1", platform=ChatPlatform.MOCK),
                text=f"M{i}", timestamp=float(i),
            )
            repo.add(msg)
        assert repo.count() == 500
        # Oldest (m0000) should be evicted
        assert repo.by_user("u1")[0].id == "m0001"

    def test_flagged_messages_tracked(self):
        repo = ChatRepository()
        msg = ChatMessage(
            id="m1", platform=ChatPlatform.MOCK,
            user=ChatUser(id="u1", display_name="U1", platform=ChatPlatform.MOCK),
            text="Bad word", timestamp=1.0,
            moderated=True, moderation_action="flag",
        )
        repo.add(msg)
        flagged = repo.flagged()
        assert len(flagged) == 1

    def test_update_moderation_clears_flagged(self):
        repo = ChatRepository()
        msg = ChatMessage(
            id="m1", platform=ChatPlatform.MOCK,
            user=ChatUser(id="u1", display_name="U1", platform=ChatPlatform.MOCK),
            text="Bad word", timestamp=1.0,
            moderated=True, moderation_action="flag",
        )
        repo.add(msg)
        assert len(repo.flagged()) == 1
        repo.update_moderation("m1", "approve")
        assert len(repo.flagged()) == 0
        updated = repo.recent(1)[0]
        assert updated.moderated is True
        assert updated.moderation_action == "approve"

    def test_update_moderation_missing_message(self):
        repo = ChatRepository()
        assert repo.update_moderation("nonexistent", "approve") is False

    def test_deduplicate_same_id(self):
        repo = ChatRepository()
        msg = ChatMessage(
            id="dup", platform=ChatPlatform.MOCK,
            user=ChatUser(id="u1", display_name="U1", platform=ChatPlatform.MOCK),
            text="First", timestamp=1.0,
        )
        repo.add(msg)
        msg2 = ChatMessage(
            id="dup", platform=ChatPlatform.MOCK,
            user=ChatUser(id="u1", display_name="U1", platform=ChatPlatform.MOCK),
            text="Second", timestamp=2.0,
        )
        repo.add(msg2)
        assert repo.count() == 1
        assert repo.recent(1)[0].text == "First"  # unchanged

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
from broadcast.audience.moderation import ModerationEngine


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


# ── MockChatBridge tests ───────────────────────────────────────────────

class TestMockChatBridge:
    @pytest.mark.asyncio
    async def test_bridge_generates_messages(self):
        from broadcast.audience.chat import MockChatBridge
        bridge = MockChatBridge(rate=10.0)  # fast rate for testing
        messages = []
        async for msg in bridge.subscribe():
            messages.append(msg)
            if len(messages) >= 3:
                break
        assert len(messages) == 3
        for msg in messages:
            assert isinstance(msg, ChatMessage)
            assert msg.platform == ChatPlatform.MOCK
            assert msg.text

    @pytest.mark.asyncio
    async def test_bridge_start_stop(self):
        from broadcast.audience.chat import MockChatBridge
        bridge = MockChatBridge(rate=10.0)
        bridge.start()
        assert bridge.running is True
        bridge.stop()
        assert bridge.running is False

    @pytest.mark.asyncio
    async def test_bridge_rejects_negative_rate(self):
        from broadcast.audience.chat import MockChatBridge
        with pytest.raises(ValueError, match="Rate must be positive"):
            MockChatBridge(rate=-1)

    def test_personas_defined(self):
        from broadcast.audience.chat import MOCK_VIEWER_PERSONAS
        assert len(MOCK_VIEWER_PERSONAS) >= 5
        for persona in MOCK_VIEWER_PERSONAS:
            assert "id" in persona
            assert "name" in persona
            assert "messages" in persona
            assert len(persona["messages"]) >= 2


# ── PollEngine tests ─────────────────────────────────────────────────────

class TestPollEngine:
    def test_create_poll(self):
        from broadcast.audience.polls import PollEngine
        engine = PollEngine()
        poll = engine.create_poll("Favorite color?", ["Red", "Blue", "Green"], 60)
        assert poll.question == "Favorite color?"
        assert poll.status == PollStatus.ACTIVE
        assert len(poll.options) == 3
        assert poll.id

    def test_vote(self):
        from broadcast.audience.polls import PollEngine
        engine = PollEngine()
        poll = engine.create_poll("Test?", ["A", "B"], 60)
        vote = engine.vote(poll.id, 0, "user1")
        assert vote.poll_id == poll.id
        assert vote.option_index == 0
        updated = engine.get_poll(poll.id)
        assert updated.options[0].votes == 1
        assert updated.options[1].votes == 0

    def test_vote_dedup(self):
        """One user can only vote once per poll."""
        from broadcast.audience.polls import PollEngine
        engine = PollEngine()
        poll = engine.create_poll("Test?", ["A", "B"], 60)
        engine.vote(poll.id, 0, "user1")
        with pytest.raises(ValueError, match="already voted"):
            engine.vote(poll.id, 1, "user1")

    def test_close_poll(self):
        from broadcast.audience.polls import PollEngine
        engine = PollEngine()
        poll = engine.create_poll("Test?", ["A", "B"], 60)
        closed = engine.close_poll(poll.id)
        assert closed.status == PollStatus.CLOSED
        assert closed.closed_at is not None

    def test_get_results(self):
        from broadcast.audience.polls import PollEngine
        engine = PollEngine()
        poll = engine.create_poll("Best?", ["Option 1", "Option 2"], 60)
        engine.vote(poll.id, 0, "u1")
        engine.vote(poll.id, 1, "u2")
        engine.vote(poll.id, 0, "u3")
        results = engine.get_results(poll.id)
        assert results["total_votes"] == 3
        assert results["options"][0]["votes"] == 2
        assert results["options"][1]["votes"] == 1
        assert results["winner"] == "Option 1"

    def test_list_polls(self):
        from broadcast.audience.polls import PollEngine
        engine = PollEngine()
        p1 = engine.create_poll("Q1?", ["A", "B"], 30)
        p2 = engine.create_poll("Q2?", ["C", "D"], 30)
        engine.close_poll(p1.id)
        all_polls = engine.list_polls(include_closed=True)
        assert len(all_polls) == 2
        active_only = engine.list_polls(include_closed=False)
        assert len(active_only) == 1
        assert active_only[0].id == p2.id

    def test_vote_on_nonexistent_poll(self):
        from broadcast.audience.polls import PollEngine
        engine = PollEngine()
        with pytest.raises(ValueError, match="not found"):
            engine.vote("nonexistent", 0, "user1")

    def test_vote_invalid_option(self):
        from broadcast.audience.polls import PollEngine
        engine = PollEngine()
        poll = engine.create_poll("Test?", ["A", "B"], 60)
        with pytest.raises(ValueError, match="Invalid option"):
            engine.vote(poll.id, 99, "user1")

    def test_auto_close_expired_poll(self):
        from broadcast.audience.polls import PollEngine
        engine = PollEngine()
        poll = engine.create_poll("Quick?", ["A", "B"], duration_seconds=0)
        # Duration 0 means already expired on next vote-triggered check
        with pytest.raises(ValueError, match="closed"):
            engine.vote(poll.id, 0, "user1")

    def test_get_active_poll(self):
        from broadcast.audience.polls import PollEngine
        engine = PollEngine()
        assert engine.get_active_poll() is None
        poll = engine.create_poll("Active?", ["A", "B"], 60)
        assert engine.get_active_poll() is not None
        engine.close_poll(poll.id)
        assert engine.get_active_poll() is None

# ── ModerationEngine tests ─────────────────────────────────────────────

class TestModerationEngine:
    def test_clean_message_passes(self):
        from broadcast.audience.moderation import ModerationEngine
        engine = ModerationEngine()
        msg = ChatMessage(
            id="m1", platform=ChatPlatform.MOCK,
            user=ChatUser(id="u1", display_name="U1", platform=ChatPlatform.MOCK),
            text="Hello everyone! This is a great stream.", timestamp=1.0,
        )
        result = engine.check(msg)
        assert result is None  # None = approved

    def test_keyword_blocklist_flags_bad_words(self):
        engine = ModerationEngine()
        engine.add_rule(ModerationRule(
            id="kr1", pattern=r"(?i)\bspam\b", action=ModerationAction.FLAG,
            reason="Spam keyword",
        ))
        msg = ChatMessage(
            id="m2", platform=ChatPlatform.MOCK,
            user=ChatUser(id="u1", display_name="U1", platform=ChatPlatform.MOCK),
            text="Check out my spam link!", timestamp=1.0,
        )
        result = engine.check(msg)
        assert result == ModerationAction.FLAG

    def test_rate_limit_exceeded(self):
        engine = ModerationEngine()
        msg = ChatMessage(
            id="m3", platform=ChatPlatform.MOCK,
            user=ChatUser(id="u1", display_name="U1", platform=ChatPlatform.MOCK),
            text="Hello", timestamp=1.0,
        )
        # First message: ok
        assert engine.check(msg) is None
        # Second within window with high rate: should be flagged
        msg2 = ChatMessage(
            id="m4", platform=ChatPlatform.MOCK,
            user=ChatUser(id="u1", display_name="U1", platform=ChatPlatform.MOCK),
            text="Hello again", timestamp=1.05,
        )
        result = engine.check(msg2)
        assert result is not None

    def test_all_caps_flagged(self):
        engine = ModerationEngine()
        msg = ChatMessage(
            id="m5", platform=ChatPlatform.MOCK,
            user=ChatUser(id="u1", display_name="U1", platform=ChatPlatform.MOCK),
            text="THIS IS A VERY LOUD MESSAGE WITH TOO MANY CAPS", timestamp=1.0,
        )
        result = engine.check(msg)
        assert result is not None

    def test_emoji_spam_flagged(self):
        engine = ModerationEngine()
        msg = ChatMessage(
            id="m6", platform=ChatPlatform.MOCK,
            user=ChatUser(id="u1", display_name="U1", platform=ChatPlatform.MOCK),
            text="\U0001f525\U0001f525\U0001f525\U0001f525\U0001f525\U0001f525\U0001f525\U0001f525\U0001f525\U0001f525\U0001f525\U0001f525\U0001f525\U0001f525", timestamp=1.0,
        )
        result = engine.check(msg)
        assert result is not None

    def test_url_flood_flagged(self):
        engine = ModerationEngine()
        msg = ChatMessage(
            id="m7", platform=ChatPlatform.MOCK,
            user=ChatUser(id="u1", display_name="U1", platform=ChatPlatform.MOCK),
            text="Check http://example.com and https://test.com and http://more.com", timestamp=1.0,
        )
        result = engine.check(msg)
        assert result is not None

    def test_rule_crud(self):
        engine = ModerationEngine()
        assert len(engine.list_rules()) == 0
        rule = ModerationRule(id="r1", pattern="bad", action=ModerationAction.FLAG, reason="Bad word")
        engine.add_rule(rule)
        assert len(engine.list_rules()) == 1
        assert engine.remove_rule("r1") is True
        assert len(engine.list_rules()) == 0

    def test_remove_nonexistent_rule(self):
        engine = ModerationEngine()
        assert engine.remove_rule("nonexistent") is False

    def test_disabled_rule_skipped(self):
        engine = ModerationEngine()
        rule = ModerationRule(id="r1", pattern=r"(?i)\btest\b", action=ModerationAction.FLAG, reason="Test", enabled=False)
        engine.add_rule(rule)
        msg = ChatMessage(
            id="m8", platform=ChatPlatform.MOCK,
            user=ChatUser(id="u1", display_name="U1", platform=ChatPlatform.MOCK),
            text="This is a test message", timestamp=1.0,
        )
        assert engine.check(msg) is None

    def test_ml_placeholder_returns_none(self):
        from broadcast.audience.moderation import ModerationEngine
        engine = ModerationEngine()
        assert engine._ml_classify("Any text") is None

    def test_missed_flag_detection(self):
        engine = ModerationEngine()
        engine.add_rule(ModerationRule(
            id="kr1", pattern=r"(?i)\bspam\b", action=ModerationAction.FLAG,
            reason="Spam",
        ))
        # 20 clean messages then a spam — the 20th triggers spot-check
        for i in range(20):
            msg = ChatMessage(
                id=f"clean_{i}", platform=ChatPlatform.MOCK,
                user=ChatUser(id="u1", display_name="U1", platform=ChatPlatform.MOCK),
                text=f"Clean message {i}", timestamp=float(i),
            )
            engine.check(msg)
        # Engine should still flag the bad message
        spam = ChatMessage(
            id="spam_1", platform=ChatPlatform.MOCK,
            user=ChatUser(id="u2", display_name="U2", platform=ChatPlatform.MOCK),
            text="This is spam", timestamp=100.0,
        )
        result = engine.check(spam)
        assert result == ModerationAction.FLAG


# ── AudienceAgent tests ────────────────────────────────────────────────

class TestAudienceAgent:
    @pytest.mark.asyncio
    async def test_agent_initial_state(self):
        from broadcast.audience.agent import AudienceAgent
        agent = AudienceAgent()
        assert agent.agent_name == "Audience"
        assert agent.agent_type == "audience"
        assert agent.running is False

    @pytest.mark.asyncio
    async def test_agent_start_stop_lifecycle(self):
        from broadcast.audience.agent import AudienceAgent
        agent = AudienceAgent()
        agent.start()
        assert agent.running is True
        agent.stop()
        assert agent.running is False

    @pytest.mark.asyncio
    async def test_get_recent_chat_returns_empty_initially(self):
        from broadcast.audience.agent import AudienceAgent
        agent = AudienceAgent()
        msgs = agent.get_recent_chat()
        assert msgs == []

    @pytest.mark.asyncio
    async def test_get_activity_summary(self):
        from broadcast.audience.agent import AudienceAgent
        agent = AudienceAgent()
        summary = agent.get_activity_summary()
        assert summary.total_messages == 0
        assert summary.unique_users == 0

    @pytest.mark.asyncio
    async def test_simulation_toggle(self):
        from broadcast.audience.agent import AudienceAgent
        agent = AudienceAgent()
        agent.start()
        await agent.start_simulation(rate=2.0)  # Fast rate so messages arrive quickly
        # Poll until messages arrive (up to 10s) instead of fixed sleep
        import asyncio
        for _ in range(20):
            await asyncio.sleep(0.5)
            msgs = agent.get_recent_chat()
            if len(msgs) > 0:
                break
        assert len(msgs) > 0
        agent.stop_simulation()
        agent.stop()

    @pytest.mark.asyncio
    async def test_get_poll_results_none_initially(self):
        from broadcast.audience.agent import AudienceAgent
        agent = AudienceAgent()
        assert agent.get_poll_results() is None


# ── API endpoint tests ────────────────────────────────────────────────

class TestAudienceAPI:
    """Test audience API endpoints via FastAPI TestClient."""

    def test_list_chat_empty(self, client):
        resp = client.get("/audience/chat", headers={"X-API-Key": "test-key"})
        assert resp.status_code == 200
        assert resp.json() == []

    def test_inject_chat(self, client):
        resp = client.post("/audience/chat", json={"text": "Hello!"}, headers={"X-API-Key": "test-key"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["text"] == "Hello!"
        assert data["platform"] == "mock"

    def test_list_chat_after_injection(self, client):
        client.post("/audience/chat", json={"text": "Hi"}, headers={"X-API-Key": "test-key"})
        resp = client.get("/audience/chat", headers={"X-API-Key": "test-key"})
        data = resp.json()
        assert len(data) >= 1
        assert any(m["text"] == "Hi" for m in data)

    def test_flag_message(self, client):
        create = client.post("/audience/chat", json={"text": "Bad word"}, headers={"X-API-Key": "test-key"})
        msg_id = create.json()["id"]
        resp = client.post(f"/audience/chat/{msg_id}/flag", headers={"X-API-Key": "test-key"})
        assert resp.status_code == 200
        assert resp.json()["flagged"] is True

    def test_flag_nonexistent_message(self, client):
        resp = client.post("/audience/chat/nonexistent/flag", headers={"X-API-Key": "test-key"})
        assert resp.status_code == 404

    def test_moderate_message(self, client):
        create = client.post("/audience/chat", json={"text": "Flag me"}, headers={"X-API-Key": "test-key"})
        msg_id = create.json()["id"]
        client.post(f"/audience/chat/{msg_id}/flag", headers={"X-API-Key": "test-key"})
        resp = client.post(f"/audience/chat/{msg_id}/moderate", json={"action": "approve"}, headers={"X-API-Key": "test-key"})
        assert resp.status_code == 200
        assert resp.json()["action"] == "approve"

    def test_moderate_invalid_action(self, client):
        create = client.post("/audience/chat", json={"text": "Hi"}, headers={"X-API-Key": "test-key"})
        msg_id = create.json()["id"]
        resp = client.post(f"/audience/chat/{msg_id}/moderate", json={"action": "invalid"}, headers={"X-API-Key": "test-key"})
        assert resp.status_code == 422

    def test_create_moderation_rule(self, client):
        resp = client.post("/audience/moderation/rules", json={
            "pattern": r"(?i)\bbadword\b",
            "action": "flag",
            "reason": "Testing",
        }, headers={"X-API-Key": "test-key"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["pattern"] == r"(?i)\bbadword\b"
        assert data["enabled"] is True

    def test_list_moderation_rules(self, client):
        resp = client.get("/audience/moderation/rules", headers={"X-API-Key": "test-key"})
        assert resp.status_code == 200

    def test_delete_moderation_rule(self, client):
        create = client.post("/audience/moderation/rules", json={
            "pattern": r"test", "action": "flag",
        }, headers={"X-API-Key": "test-key"})
        rule_id = create.json()["id"]
        resp = client.delete(f"/audience/moderation/rules/{rule_id}", headers={"X-API-Key": "test-key"})
        assert resp.status_code == 200
        assert resp.json()["deleted"] is True

    def test_delete_nonexistent_rule(self, client):
        resp = client.delete("/audience/moderation/rules/nonexistent", headers={"X-API-Key": "test-key"})
        assert resp.status_code == 404

    def test_create_poll_api(self, client):
        resp = client.post("/audience/polls", json={
            "question": "Best color?",
            "options": ["Red", "Blue", "Green"],
            "duration_seconds": 60,
        }, headers={"X-API-Key": "test-key"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["question"] == "Best color?"
        assert len(data["options"]) == 3
        assert data["status"] == "active"

    def test_vote_poll_api(self, client):
        poll = client.post("/audience/polls", json={
            "question": "Vote test?", "options": ["A", "B"], "duration_seconds": 60,
        }, headers={"X-API-Key": "test-key"}).json()
        resp = client.post(f"/audience/polls/{poll['id']}/vote", json={
            "option_index": 0, "user_id": "voter1",
        }, headers={"X-API-Key": "test-key"})
        assert resp.status_code == 200
        assert resp.json()["option_index"] == 0

    def test_vote_duplicate_returns_400(self, client):
        poll = client.post("/audience/polls", json={
            "question": "Dup test?", "options": ["A", "B"], "duration_seconds": 60,
        }, headers={"X-API-Key": "test-key"}).json()
        client.post(f"/audience/polls/{poll['id']}/vote", json={
            "option_index": 0, "user_id": "dup_voter",
        }, headers={"X-API-Key": "test-key"})
        resp = client.post(f"/audience/polls/{poll['id']}/vote", json={
            "option_index": 1, "user_id": "dup_voter",
        }, headers={"X-API-Key": "test-key"})
        assert resp.status_code == 400

    def test_close_poll_api(self, client):
        poll = client.post("/audience/polls", json={
            "question": "Close test?", "options": ["A", "B"], "duration_seconds": 60,
        }, headers={"X-API-Key": "test-key"}).json()
        resp = client.post(f"/audience/polls/{poll['id']}/close", headers={"X-API-Key": "test-key"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "closed"

    def test_audience_stats(self, client):
        resp = client.get("/audience/stats", headers={"X-API-Key": "test-key"})
        assert resp.status_code == 200
        data = resp.json()
        assert "total_messages" in data
        assert "unique_users" in data

    def test_simulation_start_stop(self, client):
        resp = client.post("/audience/simulation/start?rate=1.0", headers={"X-API-Key": "test-key"})
        assert resp.status_code == 200
        assert resp.json()["running"] is True
        resp = client.post("/audience/simulation/stop", headers={"X-API-Key": "test-key"})
        assert resp.status_code == 200
        assert resp.json()["running"] is False

    def test_api_requires_auth(self, client):
        resp = client.get("/audience/chat")
        assert resp.status_code == 403  # Forbidden (no API key)

    def test_inject_chat_empty_text_fails(self, client):
        resp = client.post("/audience/chat", json={"text": ""}, headers={"X-API-Key": "test-key"})
        assert resp.status_code == 422

    def test_create_poll_no_question_fails(self, client):
        resp = client.post("/audience/polls", json={
            "options": ["A", "B"],
        }, headers={"X-API-Key": "test-key"})
        assert resp.status_code == 422

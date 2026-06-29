"""Tests for the Memory & Personalization module — models, repository, agent, and API."""
from __future__ import annotations

import pytest
from broadcast.memory.models import (
    PersonaProfile, GuestProfile, InteractionEvent, MemoryContext,
)


class TestMemoryModels:
    def test_persona_defaults(self):
        p = PersonaProfile(id="p1", agent_type="host", name="TestHost")
        assert p.is_active is True
        assert p.usage_count == 0
        assert "friendly" in p.personality_traits
        assert p.voice_style == "casual"

    def test_persona_with_all_fields(self):
        p = PersonaProfile(
            id="p2", agent_type="cohost", name="CoHost",
            personality_traits={"witty": 0.9, "sarcastic": 0.3},
            catchphrases=["Well, well, well"], voice_style="witty",
            default_emotion="amused", emotional_range=["amused", "surprised"],
            background_story="A witty sidekick",
        )
        assert p.personality_traits["witty"] == 0.9
        assert p.catchphrases[0] == "Well, well, well"
        assert p.background_story == "A witty sidekick"

    def test_guest_defaults(self):
        g = GuestProfile(id="g1", name="Alice")
        assert g.guest_type == "one-time"
        assert g.relationship_score == 0.0
        assert g.appearance_count == 0

    def test_guest_regular(self):
        g = GuestProfile(id="g2", name="Bob", guest_type="regular", relationship_score=0.8, appearance_count=5)
        assert g.guest_type == "regular"
        assert g.relationship_score == 0.8
        assert g.appearance_count == 5

    def test_interaction_defaults(self):
        evt = InteractionEvent(id="e1", session_id="s1", timestamp=100.0, event_type="dialogue")
        assert evt.outcome == "neutral"
        assert evt.metadata == {}

    def test_interaction_with_fields(self):
        evt = InteractionEvent(
            id="e2", session_id="s1", timestamp=100.0, event_type="reaction",
            agent_involved="host", user_involved="guest", content="That was funny!",
            outcome="positive", metadata={"laughter_intensity": 0.5},
        )
        assert evt.outcome == "positive"
        assert evt.metadata["laughter_intensity"] == 0.5

    def test_memory_context_defaults(self):
        ctx = MemoryContext(id="ctx1", session_id="s1", start_time=100.0)
        assert ctx.participants == []
        assert ctx.topics_discussed == []

    def test_memory_context_roundtrip(self):
        ctx = MemoryContext(
            id="ctx1", session_id="s1", start_time=100.0, end_time=200.0,
            participants=["host", "cohost", "guest"],
            topics_discussed=["gaming", "tech"],
            key_moments=["Intro", "Discussion", "Closing"],
        )
        data = ctx.model_dump()
        restored = MemoryContext(**data)
        assert restored.session_id == "s1"
        assert "gaming" in restored.topics_discussed
        assert len(restored.key_moments) == 3


@pytest.fixture
def repo(tmp_path):
    """Create a MemoryRepository backed by a temporary file."""
    from broadcast.memory.repository import MemoryRepository
    db_path = tmp_path / "test_memory.db"
    return MemoryRepository(str(db_path))


class TestMemoryRepository:
    def test_init_creates_tables(self, repo):
        tables = repo._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        names = [r["name"] for r in tables]
        assert "personas" in names
        assert "guests" in names
        assert "interactions" in names
        assert "memory_contexts" in names

    def test_insert_and_get_persona(self, repo):
        p = PersonaProfile(id="p1", agent_type="host", name="TestHost", created_at=100.0, last_updated=100.0)
        repo.insert_persona(p)
        got = repo.get_persona("p1")
        assert got is not None
        assert got.name == "TestHost"
        assert got.personality_traits["friendly"] == 0.8

    def test_get_persona_not_found(self, repo):
        assert repo.get_persona("nonexistent") is None

    def test_update_persona(self, repo):
        p = PersonaProfile(id="p1", agent_type="host", name="TestHost", created_at=100.0, last_updated=100.0)
        repo.insert_persona(p)
        p.name = "UpdatedName"
        p.usage_count = 5
        p.last_updated = 200.0
        repo.update_persona(p)
        got = repo.get_persona("p1")
        assert got is not None
        assert got.name == "UpdatedName"
        assert got.usage_count == 5

    def test_delete_persona(self, repo):
        p = PersonaProfile(id="p1", agent_type="host", name="TestHost", created_at=100.0, last_updated=100.0)
        repo.insert_persona(p)
        assert repo.delete_persona("p1") is True
        assert repo.get_persona("p1") is None
        assert repo.delete_persona("p1") is False  # already deleted

    def test_list_personas_filter_by_type(self, repo):
        repo.insert_persona(PersonaProfile(id="p1", agent_type="host", name="H", created_at=100.0, last_updated=100.0))
        repo.insert_persona(PersonaProfile(id="p2", agent_type="cohost", name="C", created_at=100.0, last_updated=100.0))
        hosts = repo.list_personas(agent_type="host")
        assert len(hosts) == 1
        assert hosts[0].name == "H"

    def test_list_personas_active_only(self, repo):
        repo.insert_persona(PersonaProfile(id="p1", agent_type="host", name="Active", is_active=True, created_at=100.0, last_updated=100.0))
        repo.insert_persona(PersonaProfile(id="p2", agent_type="host", name="Inactive", is_active=False, created_at=100.0, last_updated=100.0))
        active = repo.list_personas(active_only=True)
        assert all(p.is_active for p in active)

    def test_guest_crud(self, repo):
        g = GuestProfile(id="g1", name="Alice", guest_type="regular", created_at=100.0, last_updated=100.0)
        repo.insert_guest(g)
        got = repo.get_guest("g1")
        assert got is not None
        assert got.name == "Alice"
        got.relationship_score = 0.9
        repo.update_guest(got)
        updated = repo.get_guest("g1")
        assert updated is not None
        assert updated.relationship_score == 0.9
        assert repo.delete_guest("g1") is True
        assert repo.get_guest("g1") is None

    def test_interaction_crud(self, repo):
        evt = InteractionEvent(id="e1", session_id="s1", timestamp=100.0, event_type="dialogue")
        repo.insert_interaction(evt)
        events = repo.query_interactions("s1")
        assert len(events) == 1
        assert events[0].event_type == "dialogue"

    def test_interaction_filter_by_type(self, repo):
        repo.insert_interaction(InteractionEvent(id="e1", session_id="s1", timestamp=100.0, event_type="dialogue"))
        repo.insert_interaction(InteractionEvent(id="e2", session_id="s1", timestamp=110.0, event_type="reaction"))
        dialogues = repo.query_interactions("s1", event_type="dialogue")
        assert len(dialogues) == 1

    def test_context_crud(self, repo):
        ctx = MemoryContext(id="ctx1", session_id="s1", start_time=100.0, participants=["host"])
        repo.insert_context(ctx)
        got = repo.get_context("s1")
        assert got is not None
        assert "host" in got.participants
        ctx.end_time = 200.0
        repo.update_context(ctx)
        updated = repo.get_context("s1")
        assert updated is not None
        assert updated.end_time == 200.0

    def test_context_not_found(self, repo):
        assert repo.get_context("nonexistent") is None

    def test_context_list(self, repo):
        repo.insert_context(MemoryContext(id="c1", session_id="s1", start_time=100.0))
        repo.insert_context(MemoryContext(id="c2", session_id="s2", start_time=200.0))
        contexts = repo.list_contexts()
        assert len(contexts) == 2

    def test_next_id_increments(self, repo):
        id1 = repo._next_id()
        id2 = repo._next_id()
        assert id1 != id2
        assert id2.endswith("_2")

    def test_close(self, repo):
        repo.close()
        repo.close()  # idempotent

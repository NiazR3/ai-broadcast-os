"""Tests for the optional SQLite persistence layer for PersonaRepository."""

import os
import tempfile

import pytest

from broadcast.agents.models import AgentType
from broadcast.agents.persona import PersonaProfile, VoiceStyle
from broadcast.agents.persona_repository import PersistentPersonaRepository


class TestPersistentPersonaRepository:
    """Tests for PersistentPersonaRepository with SQLite persistence."""

    # ── In-memory mode (no db_path) ──────────────────────────────────

    def test_in_memory_mode_init(self):
        """PersistentPersonaRepository() without db_path works as in-memory."""
        repo = PersistentPersonaRepository()
        assert repo._conn is None
        assert repo.list() == []

    def test_in_memory_crud(self):
        """Basic CRUD works without persistence."""
        repo = PersistentPersonaRepository()
        p = repo.create(name="Test", agent_type=AgentType.HOST,
                        personality_traits=[], catchphrases=[],
                        voice_style=VoiceStyle.CALM, default_emotion="ok",
                        emotional_range=["ok"])
        assert repo.get(p.id) is p
        repo.delete(p.id)
        assert repo.get(p.id) is None

    # ── SQLite persistence tests ─────────────────────────────────────

    def test_persists_across_sessions(self):
        """Data written to SQLite survives closing and reopening."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            # First session: create data
            repo = PersistentPersonaRepository(db_path)
            p1 = repo.create(name="Persistent Host", agent_type=AgentType.HOST,
                             personality_traits=["warm"], catchphrases=["Hey!"],
                             voice_style=VoiceStyle.ENERGETIC,
                             default_emotion="excited",
                             emotional_range=["excited", "calm"])
            p2 = repo.create(name="Comedy Co-Host", agent_type=AgentType.COHOST,
                             personality_traits=["funny"], catchphrases=["LOL"],
                             voice_style=VoiceStyle.WITTY,
                             default_emotion="amused",
                             emotional_range=["amused", "silly"])
            repo.close()

            # Second session: data should still be there
            repo2 = PersistentPersonaRepository(db_path)
            all_p = repo2.list()
            assert len(all_p) == 2
            names = {p.name for p in all_p}
            assert "Persistent Host" in names
            assert "Comedy Co-Host" in names

            # Verify full model integrity
            loaded = repo2.get(p1.id)
            assert loaded is not None
            assert loaded.personality_traits == ["warm"]
            assert loaded.catchphrases == ["Hey!"]
            assert loaded.voice_style == VoiceStyle.ENERGETIC
            assert loaded.emotional_range == ["excited", "calm"]
            repo2.close()
        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)

    def test_empty_repo_persists(self):
        """An empty repository with persistence loads as empty."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            # Write something, then reopen
            repo = PersistentPersonaRepository(db_path)
            repo.close()

            repo2 = PersistentPersonaRepository(db_path)
            assert repo2.list() == []
            repo2.close()
        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)

    def test_create_and_load(self):
        """Data created in one session is available in the next."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            repo = PersistentPersonaRepository(db_path)
            persona = repo.create(
                name="Morning Host",
                agent_type=AgentType.HOST,
                personality_traits=["cheerful", "warm"],
                catchphrases=["Good morning!", "Let's start the day!"],
                voice_style=VoiceStyle.ENERGETIC,
                default_emotion="cheerful",
                emotional_range=["cheerful", "serious", "thoughtful"],
                background_story="A lively morning show host with 10 years experience",
            )
            pid = persona.id
            repo.close()

            repo2 = PersistentPersonaRepository(db_path)
            loaded = repo2.get(pid)
            assert loaded is not None
            assert loaded.name == "Morning Host"
            assert loaded.personality_traits == ["cheerful", "warm"]
            assert loaded.catchphrases == ["Good morning!", "Let's start the day!"]
            assert loaded.voice_style == VoiceStyle.ENERGETIC
            assert loaded.default_emotion == "cheerful"
            assert loaded.emotional_range == ["cheerful", "serious", "thoughtful"]
            assert loaded.background_story == "A lively morning show host with 10 years experience"
            repo2.close()
        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)

    def test_update_persists(self):
        """Updates are reflected after reload."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            repo = PersistentPersonaRepository(db_path)
            p = repo.create(name="Original", agent_type=AgentType.HOST,
                            personality_traits=[], catchphrases=[],
                            voice_style=VoiceStyle.CALM, default_emotion="ok",
                            emotional_range=["ok"])
            repo.update(p.id, name="Updated", catchphrases=["New phrase!"])
            repo.close()

            repo2 = PersistentPersonaRepository(db_path)
            loaded = repo2.get(p.id)
            assert loaded is not None
            assert loaded.name == "Updated"
            assert loaded.catchphrases == ["New phrase!"]
            repo2.close()
        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)

    def test_delete_persists(self):
        """Deletions are reflected after reload."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            repo = PersistentPersonaRepository(db_path)
            p1 = repo.create(name="ToKeep", agent_type=AgentType.HOST,
                             personality_traits=[], catchphrases=[],
                             voice_style=VoiceStyle.CALM, default_emotion="ok",
                             emotional_range=["ok"])
            p2 = repo.create(name="ToDelete", agent_type=AgentType.COHOST,
                             personality_traits=[], catchphrases=[],
                             voice_style=VoiceStyle.WITTY, default_emotion="silly",
                             emotional_range=["silly"])
            repo.delete(p2.id)
            repo.close()

            repo2 = PersistentPersonaRepository(db_path)
            assert repo2.get(p1.id) is not None
            assert repo2.get(p2.id) is None
            assert len(repo2.list()) == 1
            repo2.close()
        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)

    def test_delete_missing_noop(self):
        """Deleting a nonexistent persona does nothing."""
        repo = PersistentPersonaRepository()
        assert repo.delete("ghost") is False

    def test_from_model_persists(self):
        """A persona loaded via from_model() is persisted."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            repo = PersistentPersonaRepository(db_path)
            persona = PersonaProfile(
                id="prebuilt", name="Prebuilt Host",
                agent_type=AgentType.HOST,
                personality_traits=["ready"],
                catchphrases=["Here we go!"],
                voice_style=VoiceStyle.ENERGETIC,
                default_emotion="ready",
                emotional_range=["ready", "focused"],
            )
            repo.from_model(persona)
            repo.close()

            repo2 = PersistentPersonaRepository(db_path)
            assert repo2.get("prebuilt") is not None
            assert repo2.get("prebuilt").name == "Prebuilt Host"
            repo2.close()
        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)

    def test_in_memory_no_file_created(self):
        """Without db_path, no file should be created on disk."""
        repo = PersistentPersonaRepository()
        repo.create(name="InMemory", agent_type=AgentType.HOST,
                    personality_traits=[], catchphrases=[],
                    voice_style=VoiceStyle.CALM, default_emotion="ok",
                    emotional_range=["ok"])
        repo.close()
        # No db_path was given, so no file should exist
        assert repo._conn is None

    def test_backward_compatible_dialogue_import(self):
        """PersistentPersonaRepository can be used wherever PersonaRepository is expected."""
        from broadcast.agents.persona import PersonaRepository
        repo = PersistentPersonaRepository()
        assert isinstance(repo, PersonaRepository)

import os
import tempfile
from broadcast.agents.persona_repository import PersonaRepository
from broadcast.agents.persona import PersonaProfile, VoiceStyle, AgentType


def test_repository_loads_from_file():
    # Use a temporary directory for the database file
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = os.path.join(tmp_dir, "test_repo.db")
        repo = PersonaRepository(db_path)
        # When using SQLite persistence, a new database should start empty
        assert len(repo.list()) == 0
        # Ensure the file was created
        assert os.path.exists(db_path)
        # Close the connection to allow the temporary directory to be cleaned up
        repo.close()


def test_repository_in_memory_mode():
    # Test in-memory mode (no persistence)
    repo = PersonaRepository()  # No db_path

    # Create a persona
    persona = repo.create(
        name="Test Persona",
        agent_type=AgentType.HOST,
        personality_traits=["enthusiastic", "knowledgeable"],
        catchphrases=["Let's dive in!"],
        voice_style=VoiceStyle.ENERGETIC,
        default_emotion="excited",
        emotional_range=["excited", "curious", "enthusiastic"],
        background_story="A test persona for unit testing"
    )

    assert persona.id is not None
    assert persona.name == "Test Persona"

    # Retrieve the persona
    retrieved = repo.get(persona.id)
    assert retrieved is not None
    assert retrieved.name == "Test Persona"
    assert retrieved.personality_traits == ["enthusiastic", "knowledgeable"]
    assert retrieved.catchphrases == ["Let's dive in!"]

    # List all personas
    personas = repo.list()
    assert len(personas) == 1
    assert personas[0].id == persona.id

    # Update the persona
    updated = repo.update(persona.id, name="Updated Persona")
    assert updated is not None
    assert updated.name == "Updated Persona"

    # Verify update
    retrieved_after_update = repo.get(persona.id)
    assert retrieved_after_update.name == "Updated Persona"

    # Delete the persona
    result = repo.delete(persona.id)
    assert result is True

    # Verify deletion
    assert repo.get(persona.id) is None
    assert len(repo.list()) == 0


def test_repository_persistence_across_instances():
    # Test that data persists between repository instances
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = os.path.join(tmp_dir, "persistent_repo.db")

        # Create first repository instance and add data
        repo1 = PersonaRepository(db_path)
        persona = repo1.create(
            name="Persistent Persona",
            agent_type=AgentType.COHOST,
            personality_traits=["analytical", "thorough"],
            catchphrases=["Let me break this down"],
            voice_style=VoiceStyle.PROFESSIONAL,
            default_emotion="thoughtful",
            emotional_range=["thoughtful", "analytical", "meticulous"],
            background_story="A persona that persists across instances"
        )
        persona_id = persona.id
        repo1.close()  # Important: close connection before opening another

        # Create second repository instance with same database and verify data persists
        repo2 = PersonaRepository(db_path)
        try:
            personas = repo2.list()
            assert len(personas) == 1
            assert personas[0].id == persona_id
            assert personas[0].name == "Persistent Persona"
            assert personas[0].personality_traits == ["analytical", "thorough"]
            assert personas[0].catchphrases == ["Let me break this down"]
        finally:
            repo2.close()  # Ensure cleanup


def test_repository_json_serialization():
    # Test that complex data types are properly serialized/deserialized as JSON
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = os.path.join(tmp_dir, "json_test.db")
        repo = PersonaRepository(db_path)

        # Create persona with complex data structures
        complex_traits = ["nested, list", "with, commas", "and quotes\""]
        complex_catchphrases = ['Say "hello"', "It's a 'beautiful' day"]
        complex_emotional_range = ["joy", "sorrow", "anger&joy", "fear\nanger"]

        persona = repo.create(
            name="JSON Test Persona",
            agent_type=AgentType.DIRECTOR,
            personality_traits=complex_traits,
            catchphrases=complex_catchphrases,
            voice_style=VoiceStyle.WITTY,
            default_emotion="curious",
            emotional_range=complex_emotional_range,
            background_story="A persona with complex data for JSON testing"
        )

        persona_id = persona.id
        repo.close()  # Close to ensure data is written

        # Reopen and verify data integrity
        repo2 = PersonaRepository(db_path)
        try:
            retrieved = repo2.get(persona_id)
            assert retrieved is not None
            assert retrieved.name == "JSON Test Persona"
            assert retrieved.personality_traits == complex_traits
            assert retrieved.catchphrases == complex_catchphrases
            assert retrieved.emotional_range == complex_emotional_range
            assert retrieved.background_story == "A persona with complex data for JSON testing"
        finally:
            repo2.close()


def test_repository_empty_handling():
    # Test edge cases with empty/null values
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = os.path.join(tmp_dir, "empty_test.db")
        repo = PersonaRepository(db_path)

        # Create persona with minimal data
        persona = repo.create(
            name="Minimal Persona",
            agent_type=AgentType.PRODUCER,
            personality_traits=[],  # Empty list
            catchphrases=[],        # Empty list
            voice_style=VoiceStyle.CALM,
            default_emotion="neutral",
            emotional_range=[],     # Empty list
            background_story=""     # Empty string
        )

        persona_id = persona.id
        repo.close()

        # Verify it can be retrieved correctly
        repo2 = PersonaRepository(db_path)
        try:
            retrieved = repo2.get(persona_id)
            assert retrieved is not None
            assert retrieved.name == "Minimal Persona"
            assert retrieved.personality_traits == []
            assert retrieved.catchphrases == []
            assert retrieved.emotional_range == []
            assert retrieved.background_story == ""
        finally:
            repo2.close()
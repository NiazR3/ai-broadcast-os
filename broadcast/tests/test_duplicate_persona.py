import os
import tempfile

import pytest
from broadcast.agents.persona_repository import PersonaRepository
from broadcast.agents.persona import PersonaProfile, VoiceStyle, AgentType


def test_duplicate_persona_functionality():
    """Test that duplicating a persona creates a copy with modified name"""
    # Use a temporary directory for the database
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = os.path.join(tmp_dir, "test_duplicate.db")
        repo = PersonaRepository(db_path)

        try:
            # Create a original persona
            original = repo.create(
                name="Original Persona",
                agent_type=AgentType.HOST,
                personality_traits=["enthusiastic", "knowledgeable"],
                catchphrases=["Let's dive in!"],
                voice_style=VoiceStyle.ENERGETIC,
                default_emotion="excited",
                emotional_range=["excited", "curious", "enthusiastic"],
                background_story="A test persona for unit testing"
            )

            original_id = original.id
            assert original.name == "Original Persona"

            # Duplicate the persona
            duplicated = repo.duplicate_persona(original_id)

            # Verify the duplicated persona
            assert duplicated.id != original_id  # Should have a different ID
            assert duplicated.name == "Original Persona (Copy)"  # Name should have "(Copy)" suffix
            assert duplicated.agent_type == original.agent_type
            assert duplicated.personality_traits == original.personality_traits
            assert duplicated.catchphrases == original.catchphrases
            assert duplicated.voice_style == original.voice_style
            assert duplicated.default_emotion == original.default_emotion
            assert duplicated.emotional_range == original.emotional_range
            assert duplicated.background_story == original.background_story

            # Verify both personas exist in the repository
            all_personas = repo.list()
            assert len(all_personas) == 2

            # Verify we can retrieve both by ID
            assert repo.get(original_id) is not None
            assert repo.get(duplicated.id) is not None

        finally:
            repo.close()


def test_duplicate_persona_nonexistent_id():
    """Test that duplicating a non-existent persona raises an exception"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = os.path.join(tmp_dir, "test_duplicate.db")
        repo = PersonaRepository(db_path)

        try:
            # Try to duplicate a non-existent persona
            with pytest.raises(Exception, match="non-existent"):
                repo.duplicate_persona("non-existent-id")
        finally:
            repo.close()


def test_duplicate_persona_multiple_times():
    """Test that we can duplicate a persona multiple times"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = os.path.join(tmp_dir, "test_duplicate.db")
        repo = PersonaRepository(db_path)

        try:
            # Create a original persona
            original = repo.create(
                name="Original",
                agent_type=AgentType.HOST,
                personality_traits=["test"],
                catchphrases=["test"],
                voice_style=VoiceStyle.CASUAL,
                default_emotion="neutral",
                emotional_range=["neutral"],
                background_story="test"
            )

            # Duplicate it multiple times
            duplicate1 = repo.duplicate_persona(original.id)
            duplicate2 = repo.duplicate_persona(original.id)
            duplicate3 = repo.duplicate_persona(duplicate1.id)  # Duplicate a duplicate

            # Verify all have different IDs
            ids = {original.id, duplicate1.id, duplicate2.id, duplicate3.id}
            assert len(ids) == 4  # All should be unique

            # Verify naming pattern
            assert original.name == "Original"
            assert duplicate1.name == "Original (Copy)"
            assert duplicate2.name == "Original (Copy)"
            assert duplicate3.name == "Original (Copy) (Copy)"

            # Verify we have 4 total personas
            all_personas = repo.list()
            assert len(all_personas) == 4

        finally:
            repo.close()


if __name__ == "__main__":
    test_duplicate_persona_functionality()
    test_duplicate_persona_nonexistent_id()
    test_duplicate_persona_multiple_times()
    print("All duplicate persona tests passed!")
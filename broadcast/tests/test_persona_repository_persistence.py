import os
import tempfile
from broadcast.agents.persona_repository import PersonaRepository


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
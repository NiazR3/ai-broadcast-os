"""Optional SQLite persistence for persona profiles."""
from __future__ import annotations

import json
import os
import sqlite3
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .persona import PersonaProfile


class PersonaRepository:
    """Persona repository with optional SQLite persistence.

    If db_path is provided, data is persisted to a SQLite database.
    Otherwise, data is kept in memory (default behavior for backward compatibility).
    """

    def __init__(self, db_path: Optional[str] = None) -> None:
        self._db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None
        self._personas: dict[str, PersonaProfile] = {}  # In-memory fallback

        if db_path is not None:
            self._connect()
            self._init_db()

    def _connect(self) -> None:
        """Initialize the SQLite connection."""
        # Ensure the directory exists
        db_dir = os.path.dirname(self._db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)

        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        # Enable foreign key support and WAL mode for better concurrency
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.execute("PRAGMA journal_mode=WAL")

    def _init_db(self) -> None:
        """Create the personas table if it doesn't exist."""
        if self._conn is None:
            raise RuntimeError("Database connection not initialized")
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS personas (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                agent_type TEXT NOT NULL,
                personality_traits TEXT NOT NULL,
                catchphrases TEXT NOT NULL,
                voice_style TEXT NOT NULL,
                default_emotion TEXT NOT NULL,
                emotional_range TEXT NOT NULL,
                background_story TEXT NOT NULL,
                sort_order INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        self._conn.commit()

    def _get_persona_class(self):
        """Import PersonaProfile and related enums locally to avoid circular imports cycles."""
        from .persona import PersonaProfile, AgentType, VoiceStyle

        return PersonaProfile, AgentType, VoiceStyle

    def _row_to_persona(self, row: sqlite3.Row) -> PersonaProfile:
        """Convert a database row to a PersonaProfile instance."""
        PersonaProfile, AgentType, VoiceStyle = self._get_persona_class()
        return PersonaProfile(
            id=row["id"],
            name=row["name"],
            agent_type=row["agent_type"],  # stored as string -> enum via pydantic
            personality_traits=json.loads(row["personality_traits"]),
            catchphrases=json.loads(row["catchphrases"]),
            voice_style=row["voice_style"],  # stored as string -> enum via pydantic
            default_emotion=row["default_emotion"],
            emotional_range=json.loads(row["emotional_range"]),
            background_story=row["background_story"],
            sort_order=row["sort_order"],
        )

    def _persona_to_tuple(self, persona: PersonaProfile) -> tuple:
        """Convert a PersonaProfile instance to a tuple for SQL insertion."""
        return (
            persona.id,
            persona.name,
            persona.agent_type.value,
            json.dumps(persona.personality_traits),
            json.dumps(persona.catchphrases),
            persona.voice_style.value,
            persona.default_emotion,
            json.dumps(persona.emotional_range),
            persona.background_story,
            persona.sort_order,
        )

    # CRUD operations -----------------------------------------------------

    def create(
        self,
        name: str,
        agent_type: AgentType,
        personality_traits: Optional[list[str]] = None,
        catchphrases: Optional[list[str]] = None,
        voice_style: VoiceStyle = None,
        default_emotion: str = "neutral",
        emotional_range: Optional[list[str]] = None,
        background_story: str = "",
        id: Optional[str] = None,
    ) -> PersonaProfile:
        """Create a new persona.

        If id is provided, use it (must be unique). Otherwise, generate an ID.
        """
        PersonaProfile, AgentType, VoiceStyle = self._get_persona_class()

        # Default voice_style if not provided
        if voice_style is None:
            voice_style = VoiceStyle.CASUAL

        if id is None:
            import uuid
            persona_id = uuid.uuid4().hex[:12]
        else:
            persona_id = id

        persona = PersonaProfile(
            id=persona_id,
            name=name,
            agent_type=agent_type,
            personality_traits=personality_traits or [],
            catchphrases=catchphrases or [],
            voice_style=voice_style,
            default_emotion=default_emotion,
            emotional_range=emotional_range or [],
            background_story=background_story,
        )

        if self._conn is not None:
            # Persist to SQLite
            # Use INSERT OR REPLACE to handle duplicates (mirrors from_model behavior)
            self._conn.execute(
                """
                INSERT OR REPLACE INTO personas (
                    id, name, agent_type, personality_traits, catchphrases,
                    voice_style, default_emotion, emotional_range, background_story, sort_order
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                self._persona_to_tuple(persona),
            )
            self._conn.commit()
        else:
            # In-memory storage
            self._personas[persona.id] = persona

        return persona

    def get(self, persona_id: str) -> Optional[PersonaProfile]:
        """Retrieve a persona by ID, or None if not found."""
        if self._conn is not None:
            # SQLite lookup
            cursor = self._conn.execute(
                "SELECT * FROM personas WHERE id = ?", (persona_id,)
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return self._row_to_persona(row)
        else:
            # In-memory lookup
            return self._personas.get(persona_id)

    def list(self) -> list[PersonaProfile]:
        """Return all personas."""
        if self._conn is not None:
            # SQLite query
            cursor = self._conn.execute("SELECT * FROM personas ORDER BY sort_order, id")
            rows = cursor.fetchall()
            return [self._row_to_persona(row) for row in rows]
        else:
            # In-memory list
            return list(self._personas.values())

    def update(self, persona_id: str, **kwargs) -> PersonaProfile:
        """Update fields of an existing persona."""
        PersonaProfile, AgentType, VoiceStyle = self._get_persona_class()
        persona = self.get(persona_id)
        if persona is None:
            raise ValueError(f"Persona '{persona_id}' not found")

        for key, value in kwargs.items():
            if hasattr(persona, key):
                if value is None:
                    # Reset to Pydantic field default (empty list, empty string, etc.)
                    # instead of silently skipping
                    try:
                        field_info = persona.model_fields[key]
                    except (AttributeError, KeyError):
                        continue
                    if field_info.default_factory is not None:
                        setattr(persona, key, field_info.default_factory())
                    elif field_info.default is not None:
                        import pydantic
                        if field_info.default is not pydantic.Undefined:
                            setattr(persona, key, field_info.default)
                else:
                    setattr(persona, key, value)

        if self._conn is not None:
            # Persist update to SQLite
            self._conn.execute(
                """
                UPDATE personas SET
                    name = ?, agent_type = ?, personality_traits = ?, catchphrases = ?,
                    voice_style = ?, default_emotion = ?, emotional_range = ?,
                    background_story = ?, sort_order = ?
                WHERE id = ?
                """,
                (
                    persona.name,
                    persona.agent_type.value,
                    json.dumps(persona.personality_traits),
                    json.dumps(persona.catchphrases),
                    persona.voice_style.value,
                    persona.default_emotion,
                    json.dumps(persona.emotional_range),
                    persona.background_story,
                    persona.sort_order,
                    persona.id,
                ),
            )
            self._conn.commit()
        else:
            # Update in-memory store
            self._personas[persona.id] = persona

        return persona

    def delete(self, persona_id: str) -> bool:
        """Delete a persona by ID. Returns True if deleted, False if not found."""
        if self._conn is not None:
            # SQLite delete
            cursor = self._conn.execute("DELETE FROM personas WHERE id = ?", (persona_id,))
            self._conn.commit()
            return cursor.rowcount > 0
        else:
            # In-memory delete
            if persona_id in self._personas:
                del self._personas[persona_id]
                return True
            return False

    def duplicate_persona(self, persona_id: str) -> PersonaProfile:
        """Duplicate an existing persona with a new ID and '(Copy)' suffix in name.

        Args:
            persona_id: The ID of the persona to duplicate

        Returns:
            The newly created duplicate persona

        Raises:
            ValueError: If the source persona is not found
        """
        # Get the original persona
        persona = self.get(persona_id)
        if persona is None:
            raise ValueError(f"Persona '{persona_id}' not found")

        # Import the PersonaProfile class to create a new instance
        PersonaProfile, AgentType, VoiceStyle = self._get_persona_class()

        # Create a duplicate with new ID and modified name
        duplicate = PersonaProfile(
            id=self._generate_id(),  # Generate a new ID
            name=f"{persona.name} (Copy)",
            agent_type=persona.agent_type,
            personality_traits=list(persona.personality_traits),  # Copy the list
            catchphrases=list(persona.catchphrases),  # Copy the list
            voice_style=persona.voice_style,
            default_emotion=persona.default_emotion,
            emotional_range=list(persona.emotional_range),  # Copy the list
            background_story=persona.background_story,
        )

        # Save the duplicate using the create method
        return self.create(
            name=duplicate.name,
            agent_type=duplicate.agent_type,
            personality_traits=duplicate.personality_traits,
            catchphrases=duplicate.catchphrases,
            voice_style=duplicate.voice_style,
            default_emotion=duplicate.default_emotion,
            emotional_range=duplicate.emotional_range,
            background_story=duplicate.background_story,
            id=duplicate.id,
        )

    def reorder(self, persona_ids: list[str]) -> None:
        """Update sort_order for personas based on their position in the given list.

        Args:
            persona_ids: Ordered list of persona IDs (index in list = new sort_order)
        """
        if self._conn is not None:
            for idx, pid in enumerate(persona_ids):
                self._conn.execute(
                    "UPDATE personas SET sort_order = ? WHERE id = ?",
                    (idx, pid),
                )
            self._conn.commit()
        else:
            # In-memory: update sort_order on each persona object
            for idx, pid in enumerate(persona_ids):
                if pid in self._personas:
                    persona = self._personas[pid]
                    persona.sort_order = idx

    def _generate_id(self) -> str:
        """Generate a unique ID for a persona."""
        import uuid
        return uuid.uuid4().hex[:12]

    def from_model(self, persona: PersonaProfile) -> PersonaProfile:
        """Store a pre-built PersonaProfile (used for seeding defaults).

        This method inserts the given persona, using its existing ID.
        If a persona with the same ID already exists, it is replaced.
        """
        return self.create(
            name=persona.name,
            agent_type=persona.agent_type,
            personality_traits=persona.personality_traits,
            catchphrases=persona.catchphrases,
            voice_style=persona.voice_style,
            default_emotion=persona.default_emotion,
            emotional_range=persona.emotional_range,
            background_story=persona.background_story,
            id=persona.id,
        )

    def close(self) -> None:
        """Close the database connection if applicable."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def __del__(self) -> None:
        """Ensure the database connection is closed on garbage collection."""
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:  # nosec - swallow during interpreter shutdown
                pass
            self._conn = None

    def __enter__(self) -> PersonaRepository:
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit — ensures the connection is closed."""
        self.close()
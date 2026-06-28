"""Optional SQLite-backed persistence for PersonaRepository.

Extends the in-memory PersonaRepository with optional SQLite durability.
When no db_path is provided, behaves identically to the in-memory version.

Usage:
    from broadcast.agents.persona_repository import PersistentPersonaRepository

    repo = PersistentPersonaRepository("personas.db")  # persists to disk
    repo = PersistentPersonaRepository()                # pure in-memory, same as PersonaRepository
"""

from __future__ import annotations

import json
import sqlite3
from typing import Optional

from broadcast.agents.models import AgentType
from broadcast.agents.persona import PersonaProfile, PersonaRepository, VoiceStyle


class PersistentPersonaRepository(PersonaRepository):
    """PersonaRepository with optional SQLite persistence.

    Extends the in-memory PersonaRepository: all CRUD ops work the same,
    and when a db_path is provided, they also persist to/load from SQLite.
    """

    def __init__(self, db_path: Optional[str] = None) -> None:
        super().__init__()
        self._db_path: Optional[str] = db_path
        self._conn: Optional[sqlite3.Connection] = None

        if db_path is not None:
            self._conn = sqlite3.connect(db_path)
            self._conn.row_factory = sqlite3.Row
            self._init_db()
            self._load_from_db()

    # ── SQLite schema & helpers ─────────────────────────────────────

    def _init_db(self) -> None:
        """Create the personas table if it does not exist."""
        if self._conn is None:
            return
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS personas (
                id              TEXT PRIMARY KEY,
                name            TEXT NOT NULL,
                agent_type      TEXT NOT NULL,
                personality_traits  TEXT DEFAULT '[]',
                catchphrases    TEXT DEFAULT '[]',
                voice_style     TEXT NOT NULL DEFAULT 'casual',
                default_emotion TEXT NOT NULL DEFAULT 'neutral',
                emotional_range TEXT DEFAULT '[]',
                background_story TEXT DEFAULT ''
            )
            """
        )
        self._conn.commit()

    def _load_from_db(self) -> None:
        """Hydrate the in-memory dict from the SQLite database."""
        if self._conn is None:
            return
        cursor = self._conn.execute("SELECT * FROM personas")
        for row in cursor.fetchall():
            persona = PersonaProfile(
                id=row["id"],
                name=row["name"],
                agent_type=AgentType(row["agent_type"]),
                personality_traits=json.loads(row["personality_traits"] or "[]"),
                catchphrases=json.loads(row["catchphrases"] or "[]"),
                voice_style=VoiceStyle(row["voice_style"]),
                default_emotion=row["default_emotion"],
                emotional_range=json.loads(row["emotional_range"] or "[]"),
                background_story=row["background_story"] or "",
            )
            self._personas[persona.id] = persona

    def _upsert_db(self, persona: PersonaProfile) -> None:
        """Insert or replace a persona row in SQLite."""
        if self._conn is None:
            return
        self._conn.execute(
            """
            INSERT OR REPLACE INTO personas
                (id, name, agent_type, personality_traits, catchphrases,
                 voice_style, default_emotion, emotional_range, background_story)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                persona.id,
                persona.name,
                persona.agent_type.value,
                json.dumps(persona.personality_traits),
                json.dumps(persona.catchphrases),
                persona.voice_style.value,
                persona.default_emotion,
                json.dumps(persona.emotional_range),
                persona.background_story,
            ),
        )
        self._conn.commit()

    def _delete_db(self, persona_id: str) -> None:
        """Remove a persona row from SQLite."""
        if self._conn is None:
            return
        self._conn.execute("DELETE FROM personas WHERE id = ?", (persona_id,))
        self._conn.commit()

    # ── Override CRUD to persist ────────────────────────────────────

    def create(
        self,
        name: str,
        agent_type: AgentType,
        personality_traits: Optional[list[str]] = None,
        catchphrases: Optional[list[str]] = None,
        voice_style: VoiceStyle = VoiceStyle.CASUAL,
        default_emotion: str = "neutral",
        emotional_range: Optional[list[str]] = None,
        background_story: str = "",
    ) -> PersonaProfile:
        persona = super().create(
            name=name,
            agent_type=agent_type,
            personality_traits=personality_traits,
            catchphrases=catchphrases,
            voice_style=voice_style,
            default_emotion=default_emotion,
            emotional_range=emotional_range,
            background_story=background_story,
        )
        self._upsert_db(persona)
        return persona

    def from_model(self, persona: PersonaProfile) -> PersonaProfile:
        persona = super().from_model(persona)
        self._upsert_db(persona)
        return persona

    def update(self, persona_id: str, **kwargs) -> PersonaProfile:
        persona = super().update(persona_id, **kwargs)
        self._upsert_db(persona)
        return persona

    def delete(self, persona_id: str) -> bool:
        deleted = super().delete(persona_id)
        if deleted:
            self._delete_db(persona_id)
        return deleted

    def close(self) -> None:
        """Close the database connection (cleanup)."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None

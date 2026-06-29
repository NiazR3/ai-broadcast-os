"""SQLite-backed persistence for memory data — personas, guests, interactions, contexts."""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
from time import time
from typing import Optional

from broadcast.memory.models import (
    GuestProfile, InteractionEvent, MemoryContext, PersonaProfile,
)

logger = logging.getLogger(__name__)


class MemoryRepository:
    """SQLite-backed store for persona, guest, interaction, and context data.

    Uses WAL mode for concurrent read/write. Follows the same pattern as
    AnalyticsDatabase in the analytics module.
    """

    DB_DIR = "broadcast_data"
    DB_FILENAME = "memory.db"

    def __init__(self, db_path: Optional[str] = None) -> None:
        self._db_path = db_path or os.path.join(self.DB_DIR, self.DB_FILENAME)
        self._local = threading.local()
        self._lock = threading.Lock()
        self._id_counter: int = 0
        self._ensure_dir()
        self._init_db()

    @property
    def _conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(self._db_path)
            self._local.conn.row_factory = sqlite3.Row
            self._local.conn.execute("PRAGMA journal_mode=WAL")
            self._local.conn.execute("PRAGMA foreign_keys=ON")
        return self._local.conn

    def _ensure_dir(self) -> None:
        db_dir = os.path.dirname(self._db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)

    def _init_db(self) -> None:
        with self._lock:
            cur = self._conn.cursor()
            cur.executescript("""
                CREATE TABLE IF NOT EXISTS personas (
                    id TEXT PRIMARY KEY,
                    agent_type TEXT NOT NULL,
                    name TEXT DEFAULT '',
                    personality_traits TEXT DEFAULT '{}',
                    catchphrases TEXT DEFAULT '[]',
                    voice_style TEXT DEFAULT 'casual',
                    default_emotion TEXT DEFAULT 'neutral',
                    emotional_range TEXT DEFAULT '["neutral","happy","excited"]',
                    background_story TEXT DEFAULT '',
                    is_active INTEGER DEFAULT 1,
                    usage_count INTEGER DEFAULT 0,
                    created_at REAL DEFAULT 0,
                    last_updated REAL DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS guests (
                    id TEXT PRIMARY KEY,
                    name TEXT DEFAULT '',
                    guest_type TEXT DEFAULT 'one-time',
                    relationship_score REAL DEFAULT 0,
                    topics_of_interest TEXT DEFAULT '[]',
                    special_notes TEXT DEFAULT '',
                    appearance_count INTEGER DEFAULT 0,
                    last_appearance REAL,
                    created_at REAL DEFAULT 0,
                    last_updated REAL DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS interactions (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    event_type TEXT NOT NULL,
                    agent_involved TEXT DEFAULT '',
                    user_involved TEXT DEFAULT '',
                    content TEXT DEFAULT '',
                    outcome TEXT DEFAULT 'neutral',
                    metadata TEXT DEFAULT '{}'
                );

                CREATE TABLE IF NOT EXISTS memory_contexts (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    start_time REAL NOT NULL,
                    end_time REAL,
                    participants TEXT DEFAULT '[]',
                    topics_discussed TEXT DEFAULT '[]',
                    emotional_arc TEXT DEFAULT '[]',
                    key_moments TEXT DEFAULT '[]',
                    feedback_received TEXT DEFAULT '[]'
                );

                CREATE INDEX IF NOT EXISTS idx_personas_type ON personas(agent_type);
                CREATE INDEX IF NOT EXISTS idx_personas_active ON personas(is_active);
                CREATE INDEX IF NOT EXISTS idx_interactions_session ON interactions(session_id);
                CREATE INDEX IF NOT EXISTS idx_interactions_type ON interactions(event_type);
                CREATE INDEX IF NOT EXISTS idx_contexts_session ON memory_contexts(session_id);
            """)
            self._conn.commit()

    def _next_id(self, prefix: str = "mem") -> str:
        self._id_counter += 1
        return f"{prefix}_{int(time() * 1000)}_{self._id_counter}"

    # ── Persona CRUD ─────────────────────────────────────────────────

    def insert_persona(self, persona: PersonaProfile) -> None:
        with self._lock:
            self._conn.execute(
                """INSERT INTO personas (id, agent_type, name, personality_traits, catchphrases,
                   voice_style, default_emotion, emotional_range, background_story,
                   is_active, usage_count, created_at, last_updated)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (persona.id, persona.agent_type, persona.name,
                 json.dumps(persona.personality_traits), json.dumps(persona.catchphrases),
                 persona.voice_style, persona.default_emotion,
                 json.dumps(persona.emotional_range), persona.background_story,
                 1 if persona.is_active else 0, persona.usage_count,
                 persona.created_at, persona.last_updated),
            )
            self._conn.commit()

    def get_persona(self, persona_id: str) -> Optional[PersonaProfile]:
        row = self._conn.execute(
            "SELECT * FROM personas WHERE id = ?", (persona_id,),
        ).fetchone()
        if row is None:
            return None
        return self._row_to_persona(row)

    def list_personas(
        self, agent_type: Optional[str] = None, active_only: bool = True,
    ) -> list[PersonaProfile]:
        if agent_type and active_only:
            rows = self._conn.execute(
                "SELECT * FROM personas WHERE agent_type = ? AND is_active = 1 ORDER BY created_at DESC",
                (agent_type,),
            ).fetchall()
        elif agent_type:
            rows = self._conn.execute(
                "SELECT * FROM personas WHERE agent_type = ? ORDER BY created_at DESC",
                (agent_type,),
            ).fetchall()
        elif active_only:
            rows = self._conn.execute(
                "SELECT * FROM personas WHERE is_active = 1 ORDER BY created_at DESC",
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM personas ORDER BY created_at DESC",
            ).fetchall()
        return [self._row_to_persona(r) for r in rows]

    def update_persona(self, persona: PersonaProfile) -> None:
        with self._lock:
            self._conn.execute(
                """UPDATE personas SET agent_type=?, name=?, personality_traits=?, catchphrases=?,
                   voice_style=?, default_emotion=?, emotional_range=?, background_story=?,
                   is_active=?, usage_count=?, last_updated=?
                   WHERE id=?""",
                (persona.agent_type, persona.name, json.dumps(persona.personality_traits),
                 json.dumps(persona.catchphrases), persona.voice_style,
                 persona.default_emotion, json.dumps(persona.emotional_range),
                 persona.background_story, 1 if persona.is_active else 0,
                 persona.usage_count, persona.last_updated, persona.id),
            )
            self._conn.commit()

    def delete_persona(self, persona_id: str) -> bool:
        with self._lock:
            cur = self._conn.execute("DELETE FROM personas WHERE id = ?", (persona_id,))
            self._conn.commit()
            return cur.rowcount > 0

    # ── Guest CRUD ───────────────────────────────────────────────────

    def insert_guest(self, guest: GuestProfile) -> None:
        with self._lock:
            self._conn.execute(
                """INSERT INTO guests (id, name, guest_type, relationship_score,
                   topics_of_interest, special_notes, appearance_count, last_appearance,
                   created_at, last_updated)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (guest.id, guest.name, guest.guest_type, guest.relationship_score,
                 json.dumps(guest.topics_of_interest), guest.special_notes,
                 guest.appearance_count, guest.last_appearance,
                 guest.created_at, guest.last_updated),
            )
            self._conn.commit()

    def get_guest(self, guest_id: str) -> Optional[GuestProfile]:
        row = self._conn.execute(
            "SELECT * FROM guests WHERE id = ?", (guest_id,),
        ).fetchone()
        if row is None:
            return None
        return self._row_to_guest(row)

    def list_guests(self, guest_type: Optional[str] = None) -> list[GuestProfile]:
        if guest_type:
            rows = self._conn.execute(
                "SELECT * FROM guests WHERE guest_type = ? ORDER BY last_updated DESC",
                (guest_type,),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM guests ORDER BY last_updated DESC",
            ).fetchall()
        return [self._row_to_guest(r) for r in rows]

    def update_guest(self, guest: GuestProfile) -> None:
        with self._lock:
            self._conn.execute(
                """UPDATE guests SET name=?, guest_type=?, relationship_score=?,
                   topics_of_interest=?, special_notes=?, appearance_count=?,
                   last_appearance=?, last_updated=? WHERE id=?""",
                (guest.name, guest.guest_type, guest.relationship_score,
                 json.dumps(guest.topics_of_interest), guest.special_notes,
                 guest.appearance_count, guest.last_appearance,
                 guest.last_updated, guest.id),
            )
            self._conn.commit()

    def delete_guest(self, guest_id: str) -> bool:
        with self._lock:
            cur = self._conn.execute("DELETE FROM guests WHERE id = ?", (guest_id,))
            self._conn.commit()
            return cur.rowcount > 0

    # ── Interaction CRUD ─────────────────────────────────────────────

    def insert_interaction(self, evt: InteractionEvent) -> None:
        with self._lock:
            self._conn.execute(
                """INSERT INTO interactions (id, session_id, timestamp, event_type,
                   agent_involved, user_involved, content, outcome, metadata)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (evt.id, evt.session_id, evt.timestamp, evt.event_type,
                 evt.agent_involved, evt.user_involved, evt.content,
                 evt.outcome, json.dumps(evt.metadata)),
            )
            self._conn.commit()

    def query_interactions(
        self, session_id: str, event_type: Optional[str] = None, limit: int = 200,
    ) -> list[InteractionEvent]:
        if event_type:
            rows = self._conn.execute(
                "SELECT * FROM interactions WHERE session_id = ? AND event_type = ? ORDER BY timestamp ASC LIMIT ?",
                (session_id, event_type, limit),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM interactions WHERE session_id = ? ORDER BY timestamp ASC LIMIT ?",
                (session_id, limit),
            ).fetchall()
        return [self._row_to_interaction(r) for r in rows]

    # ── Memory Context CRUD ──────────────────────────────────────────

    def insert_context(self, ctx: MemoryContext) -> None:
        with self._lock:
            self._conn.execute(
                """INSERT INTO memory_contexts (id, session_id, start_time, end_time,
                   participants, topics_discussed, emotional_arc, key_moments, feedback_received)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (ctx.id, ctx.session_id, ctx.start_time, ctx.end_time,
                 json.dumps(ctx.participants), json.dumps(ctx.topics_discussed),
                 json.dumps(ctx.emotional_arc), json.dumps(ctx.key_moments),
                 json.dumps(ctx.feedback_received)),
            )
            self._conn.commit()

    def get_context(self, session_id: str) -> Optional[MemoryContext]:
        row = self._conn.execute(
            "SELECT * FROM memory_contexts WHERE session_id = ? ORDER BY start_time DESC LIMIT 1",
            (session_id,),
        ).fetchone()
        if row is None:
            return None
        return self._row_to_context(row)

    def update_context(self, ctx: MemoryContext) -> None:
        with self._lock:
            self._conn.execute(
                """UPDATE memory_contexts SET start_time=?, end_time=?, participants=?,
                   topics_discussed=?, emotional_arc=?, key_moments=?, feedback_received=?
                   WHERE id=?""",
                (ctx.start_time, ctx.end_time, json.dumps(ctx.participants),
                 json.dumps(ctx.topics_discussed), json.dumps(ctx.emotional_arc),
                 json.dumps(ctx.key_moments), json.dumps(ctx.feedback_received), ctx.id),
            )
            self._conn.commit()

    def list_contexts(self, limit: int = 20) -> list[MemoryContext]:
        rows = self._conn.execute(
            "SELECT * FROM memory_contexts ORDER BY start_time DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [self._row_to_context(r) for r in rows]

    # ── Row deserialization helpers ──────────────────────────────────

    @staticmethod
    def _row_to_persona(row: sqlite3.Row) -> PersonaProfile:
        return PersonaProfile(
            id=row["id"], agent_type=row["agent_type"], name=row["name"],
            personality_traits=json.loads(row["personality_traits"]),
            catchphrases=json.loads(row["catchphrases"]),
            voice_style=row["voice_style"], default_emotion=row["default_emotion"],
            emotional_range=json.loads(row["emotional_range"]),
            background_story=row["background_story"],
            is_active=bool(row["is_active"]), usage_count=row["usage_count"],
            created_at=row["created_at"], last_updated=row["last_updated"],
        )

    @staticmethod
    def _row_to_guest(row: sqlite3.Row) -> GuestProfile:
        return GuestProfile(
            id=row["id"], name=row["name"], guest_type=row["guest_type"],
            relationship_score=row["relationship_score"],
            topics_of_interest=json.loads(row["topics_of_interest"]),
            special_notes=row["special_notes"],
            appearance_count=row["appearance_count"],
            last_appearance=row["last_appearance"],
            created_at=row["created_at"], last_updated=row["last_updated"],
        )

    @staticmethod
    def _row_to_interaction(row: sqlite3.Row) -> InteractionEvent:
        return InteractionEvent(
            id=row["id"], session_id=row["session_id"], timestamp=row["timestamp"],
            event_type=row["event_type"], agent_involved=row["agent_involved"],
            user_involved=row["user_involved"], content=row["content"],
            outcome=row["outcome"], metadata=json.loads(row["metadata"]),
        )

    @staticmethod
    def _row_to_context(row: sqlite3.Row) -> MemoryContext:
        return MemoryContext(
            id=row["id"], session_id=row["session_id"], start_time=row["start_time"],
            end_time=row["end_time"],
            participants=json.loads(row["participants"]),
            topics_discussed=json.loads(row["topics_discussed"]),
            emotional_arc=json.loads(row["emotional_arc"]),
            key_moments=json.loads(row["key_moments"]),
            feedback_received=json.loads(row["feedback_received"]),
        )

    def close(self) -> None:
        if hasattr(self._local, "conn") and self._local.conn:
            self._local.conn.close()
            self._local.conn = None

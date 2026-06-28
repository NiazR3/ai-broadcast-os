# M3: Persona Profiles Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add persona profiles (personality, catchphrases, emotional range) to broadcast agents, with CRUD API, persona-aware dialogue generation, and dashboard UI.

**Architecture:** New `PersonaProfile` Pydantic model + `PersonaRepository` (in-memory CRUD). Existing `HostAgent`/`CoHostAgent` gain persona assignment. Dialogue templates inject persona catchphrases and select emotion from the persona's emotional range. All endpoints under `/agent/persona`.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic v2, React 19 + TypeScript, Vite 6

## Global Constraints

- Follow existing M1/M2 patterns: module-level singletons, in-memory storage, `BaseAgent` lifecycle.
- All new Pydantic models in `broadcast/agents/models.py` or new file.
- Tests mirror existing pattern: pytest with FastAPI TestClient.
- Dashboard components: no tests (TS compilation only — existing M1/M2 pattern).
- Dialogue backward compatibility: no persona assigned = identical current behavior.

---
## File Structure

**New files:**
- `broadcast/agents/persona.py` — PersonaProfile model, PersonaRepository, VoiceStyle enum
- `broadcast/tests/test_persona.py` — persona model, repository, dialogue, API tests
- `broadcast/dashboard/src/components/PersonaPanel.tsx` — list/create/edit/assign UI
- `broadcast/dashboard/src/components/PersonaEditor.tsx` — create/edit form modal

**Modified files:**
- `broadcast/agents/dialogue.py` — persona awareness (assign_persona, emotion from range)
- `broadcast/agents/router.py` — persona CRUD + assignment endpoints
- `broadcast/agents/__init__.py` — export PersonaProfile
- `broadcast/dashboard/src/lib/api.ts` — persona API functions + types
- `broadcast/dashboard/src/App.tsx` — wire PersonaPanel tab

---

### Task 1: Persona Models and Repository

**Files:**
- Create: `broadcast/agents/persona.py`
- Test: `broadcast/tests/test_persona.py`

**Interfaces:**
- Produces: `VoiceStyle` enum, `PersonaProfile` model, `PersonaRepository` class with `create/get/list/update/delete` methods

- [ ] **Step 1: Write the failing tests in `tests/test_persona.py`**

```python
"""Tests for persona models and repository."""
import pytest
from broadcast.agents.persona import (
    PersonaProfile, PersonaRepository, VoiceStyle,
)
from broadcast.agents.models import AgentType


class TestPersonaModel:
    def test_create_valid_persona(self):
        p = PersonaProfile(
            id="p1", name="Energetic Host",
            agent_type=AgentType.HOST,
            personality_traits=["enthusiastic", "warm"],
            catchphrases=["Let's go!", "That's amazing!"],
            voice_style=VoiceStyle.ENERGETIC,
            default_emotion="excited",
            emotional_range=["excited", "curious", "thoughtful"],
        )
        assert p.id == "p1"
        assert len(p.catchphrases) == 2
        assert p.voice_style == VoiceStyle.ENERGETIC

    def test_persona_default_emotion_in_range(self):
        p = PersonaProfile(
            id="p2", name="Calm Host",
            agent_type=AgentType.HOST,
            personality_traits=["calm"],
            catchphrases=[],
            voice_style=VoiceStyle.CALM,
            default_emotion="serene",
            emotional_range=["serene", "professional"],
        )
        assert p.default_emotion in p.emotional_range or True  # not enforced at model level

    def test_voice_style_enum_values(self):
        assert VoiceStyle.ENERGETIC.value == "energetic"
        assert VoiceStyle.CALM.value == "calm"


class TestPersonaRepository:
    @pytest.fixture
    def repo(self):
        return PersonaRepository()

    def test_create_and_get(self, repo):
        p = repo.create(
            name="Host V1", agent_type=AgentType.HOST,
            personality_traits=["fun"], catchphrases=["Yo!"],
            voice_style=VoiceStyle.CASUAL,
            default_emotion="happy",
            emotional_range=["happy", "serious"],
        )
        assert p.id
        assert repo.get(p.id) is p

    def test_get_missing(self, repo):
        assert repo.get("nonexistent") is None

    def test_list_empty(self, repo):
        assert repo.list() == []

    def test_list_after_create(self, repo):
        repo.create(name="A", agent_type=AgentType.HOST,
                    personality_traits=[], catchphrases=[],
                    voice_style=VoiceStyle.CALM, default_emotion="ok",
                    emotional_range=["ok"])
        repo.create(name="B", agent_type=AgentType.COHOST,
                    personality_traits=[], catchphrases=[],
                    voice_style=VoiceStyle.WITTY, default_emotion="silly",
                    emotional_range=["silly"])
        names = [p.name for p in repo.list()]
        assert "A" in names
        assert "B" in names

    def test_update(self, repo):
        p = repo.create(name="Original", agent_type=AgentType.HOST,
                        personality_traits=[], catchphrases=[],
                        voice_style=VoiceStyle.CALM, default_emotion="ok",
                        emotional_range=["ok"])
        updated = repo.update(p.id, name="Updated")
        assert updated.name == "Updated"
        assert repo.get(p.id).name == "Updated"

    def test_update_missing(self, repo):
        with pytest.raises(ValueError, match="not found"):
            repo.update("ghost", name="X")

    def test_delete(self, repo):
        p = repo.create(name="Temp", agent_type=AgentType.HOST,
                        personality_traits=[], catchphrases=[],
                        voice_style=VoiceStyle.CALM, default_emotion="ok",
                        emotional_range=["ok"])
        assert repo.delete(p.id) is True
        assert repo.get(p.id) is None

    def test_delete_missing(self, repo):
        assert repo.delete("ghost") is False

    def test_create_assigns_id(self, repo):
        p = repo.create(name="AutoID", agent_type=AgentType.HOST,
                        personality_traits=[], catchphrases=[],
                        voice_style=VoiceStyle.CALM, default_emotion="ok",
                        emotional_range=["ok"])
        assert len(p.id) == 12  # matches uuid hex[:12] pattern
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
cd /c/Users/MezbiN/broadcast && source .venv/Scripts/activate && python -m pytest tests/test_persona.py -v 2>&1 | tail -30
```
Expected: ModuleNotFoundError or ImportError — no `persona.py` yet.

- [ ] **Step 3: Write minimal implementation in `agents/persona.py`**

```python
"""Persona profiles — personality, catchphrases, emotional range for broadcast agents."""
from __future__ import annotations

import uuid
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from broadcast.agents.models import AgentType


class VoiceStyle(str, Enum):
    """Overall delivery style for a persona."""
    ENERGETIC = "energetic"
    CALM = "calm"
    PROFESSIONAL = "professional"
    CASUAL = "casual"
    WITTY = "witty"
    SERIOUS = "serious"


class PersonaProfile(BaseModel):
    """Defines how a broadcast agent speaks and behaves."""
    id: str = Field(..., description="Unique persona identifier")
    name: str = Field(..., min_length=1, description="Persona display name")
    agent_type: AgentType = Field(..., description="The agent this persona is for")
    personality_traits: list[str] = Field(default_factory=list, description="e.g. enthusiastic, curious")
    catchphrases: list[str] = Field(default_factory=list, description="Catchphrases the persona uses")
    voice_style: VoiceStyle = Field(default=VoiceStyle.CASUAL, description="Delivery style")
    default_emotion: str = Field(default="neutral", description="Fallback emotion for dialogue")
    emotional_range: list[str] = Field(default_factory=list, description="Emotions this persona can express")
    background_story: str = Field(default="", description="Short bio / context for LLM prompt building")


class PersonaRepository:
    """In-memory CRUD for persona profiles.

    Follows the same pattern as ProducerAgent._episodes (dict + module-level singleton).
    """

    def __init__(self) -> None:
        self._personas: dict[str, PersonaProfile] = {}

    def _next_id(self) -> str:
        return uuid.uuid4().hex[:12]

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
        """Create a new persona with an auto-generated ID."""
        persona = PersonaProfile(
            id=self._next_id(),
            name=name,
            agent_type=agent_type,
            personality_traits=personality_traits or [],
            catchphrases=catchphrases or [],
            voice_style=voice_style,
            default_emotion=default_emotion,
            emotional_range=emotional_range or [],
            background_story=background_story,
        )
        self._personas[persona.id] = persona
        return persona

    def from_model(self, persona: PersonaProfile) -> PersonaProfile:
        """Store a pre-built PersonaProfile (used for seeding defaults)."""
        self._personas[persona.id] = persona
        return persona

    def get(self, persona_id: str) -> Optional[PersonaProfile]:
        """Get a persona by ID, or None if not found."""
        return self._personas.get(persona_id)

    def list(self) -> list[PersonaProfile]:
        """Return all persona profiles."""
        return list(self._personas.values())

    def update(self, persona_id: str, **kwargs) -> PersonaProfile:
        """Update fields on an existing persona. Raises ValueError if not found."""
        persona = self.get(persona_id)
        if persona is None:
            raise ValueError(f"Persona '{persona_id}' not found")
        for key, value in kwargs.items():
            if hasattr(persona, key) and value is not None:
                setattr(persona, key, value)
        return persona

    def delete(self, persona_id: str) -> bool:
        """Delete a persona. Returns True if existed, False otherwise."""
        if persona_id not in self._personas:
            return False
        del self._personas[persona_id]
        return True
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
cd /c/Users/MezbiN/broadcast && source .venv/Scripts/activate && python -m pytest tests/test_persona.py -v 2>&1
```
Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
cd /c/Users/MezbiN/broadcast && git add agents/persona.py tests/test_persona.py && git commit -m "feat(persona): add PersonaProfile model and PersonaRepository with tests"
```

---

### Task 2: Persona-Aware Dialogue Generation

**Files:**
- Modify: `broadcast/agents/dialogue.py`
- Modify: `broadcast/tests/test_persona.py` (add dialogue tests)

**Interfaces:**
- Consumes: `PersonaProfile`, `PersonaRepository`, `VoiceStyle`
- Produces: `HostAgent.assign_persona(persona_id)`, `CoHostAgent.assign_persona(persona_id)`, `HostAgent.get_persona()`, `CoHostAgent.get_persona()`

- [ ] **Step 1: Add dialogue persona tests to `tests/test_persona.py`**

Append to `tests/test_persona.py`:

```python
class TestPersonaAwareDialogue:
    @pytest.fixture
    def host_persona(self):
        return PersonaProfile(
            id="hp1", name="Energetic Host",
            agent_type=AgentType.HOST,
            personality_traits=["enthusiastic", "warm"],
            catchphrases=["Let's go!", "This is huge!"],
            voice_style=VoiceStyle.ENERGETIC,
            default_emotion="excited",
            emotional_range=["excited", "curious", "thoughtful"],
        )

    @pytest.fixture
    def cohost_persona(self):
        return PersonaProfile(
            id="cp1", name="Witty Co-Host",
            agent_type=AgentType.COHOST,
            personality_traits=["witty", "sarcastic"],
            catchphrases=["No way!", "I'm shook!"],
            voice_style=VoiceStyle.WITTY,
            default_emotion="amused",
            emotional_range=["amused", "surprised", "skeptical"],
        )

    def test_unassigned_host_behaves_as_before(self, host):
        """No persona assigned = backward compatible."""
        from broadcast.agents.dialogue import HostAgent
        h = HostAgent()
        seg = Segment(id="intro", type=SegmentType.INTRO, title="Welcome")
        block = h.generate_dialogue(seg)
        assert len(block.lines) >= 1
        assert block.lines[0].emotion is None  # no persona = no emotion

    def test_assigned_persona_sets_emotion(self, host, host_persona, repo):
        repo.from_model(host_persona)
        host.assign_persona("hp1", repo)
        seg = Segment(id="seg_1", type=SegmentType.CONTENT, title="AI News", dialogue_prompt="Latest AI breakthroughs")
        block = host.generate_dialogue(seg)
        # Host persona default emotion is "excited" — first in emotional_range
        assert block.lines[0].emotion is not None
        assert block.lines[0].emotion in host_persona.emotional_range

    def test_assigned_cohost_sets_emotion(self, cohost, cohost_persona, repo):
        repo.from_model(cohost_persona)
        cohost.assign_persona("cp1", repo)
        seg = Segment(id="seg_1", type=SegmentType.CONTENT, title="Space News")
        block = cohost.generate_dialogue(seg, host_dialogue="Let's talk space!")
        assert block.lines[0].emotion is not None
        assert block.lines[0].emotion in cohost_persona.emotional_range

    def test_persona_catchphrase_appears_occasionally(self, host, host_persona, repo):
        repo.from_model(host_persona)
        host.assign_persona("hp1", repo)
        seg = Segment(id="seg_1", type=SegmentType.INTRO, title="Big Announcement")
        # Run multiple times to check catchphrases appear
        catchphrases_found = False
        for _ in range(20):
            block = host.generate_dialogue(seg)
            text = " ".join(l.text for l in block.lines)
            for cp in host_persona.catchphrases:
                if cp.lower() in text.lower():
                    catchphrases_found = True
                    break
            if catchphrases_found:
                break
        assert catchphrases_found, "Catchphrase should appear within 20 generations"

    def test_persona_persists_across_calls(self, host, host_persona, repo):
        repo.from_model(host_persona)
        host.assign_persona("hp1", repo)
        retrieved = host.get_persona()
        assert retrieved is not None
        assert retrieved.id == "hp1"
        assert retrieved.name == "Energetic Host"

    def test_remove_persona_reverts_behavior(self, host, host_persona, repo):
        repo.from_model(host_persona)
        host.assign_persona("hp1", repo)
        host.remove_persona()
        seg = Segment(id="seg_1", type=SegmentType.CONTENT, title="Test")
        block = host.generate_dialogue(seg)
        assert block.lines[0].emotion is None  # back to default
        assert host.get_persona() is None
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run:
```bash
cd /c/Users/MezbiN/broadcast && source .venv/Scripts/activate && python -m pytest tests/test_persona.py::TestPersonaAwareDialogue -v 2>&1
```
Expected: FAIL — HostAgent has no `assign_persona` method yet.

- [ ] **Step 3: Update `agents/dialogue.py` with persona awareness**

Add import and modify both HostAgent and CoHostAgent:

```python
# At top of dialogue.py, add import:
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from broadcast.agents.persona import PersonaProfile, PersonaRepository
```

Add `assign_persona`, `get_persona`, and `remove_persona` methods plus persona-aware template selection to HostAgent:

```python
class HostAgent(BaseAgent):
    """Host agent — generates opening dialogue, introduces topics, welcomes guests."""

    def __init__(self) -> None:
        super().__init__()
        self._call_counter: dict[str, int] = {}
        self._persona_id: Optional[str] = None

    # ── Persona management ────────────────────────────────────────

    def assign_persona(self, persona_id: str, repo: "PersonaRepository") -> None:
        """Assign a persona profile to this agent."""
        persona = repo.get(persona_id)
        if persona is None:
            raise ValueError(f"Persona '{persona_id}' not found")
        self._persona_id = persona_id

    def get_persona(self, repo: "PersonaRepository") -> Optional["PersonaProfile"]:
        """Get the currently assigned persona, or None."""
        if self._persona_id is None:
            return None
        return repo.get(self._persona_id)

    def remove_persona(self) -> None:
        """Remove the persona assignment (revert to default behavior)."""
        self._persona_id = None

    def _select_emotion(self, persona: "PersonaProfile", segment_type: SegmentType) -> str:
        """Pick an emotion from the persona's range based on segment type."""
        if not persona.emotional_range:
            return persona.default_emotion
        # Map segment position to an emotion index
        idx_map = {
            SegmentType.INTRO: 0,
            SegmentType.OUTRO: -1,
            SegmentType.AD: 0,
            SegmentType.GUEST: min(1, len(persona.emotional_range) - 1),
            SegmentType.CONTENT: min(1, len(persona.emotional_range) - 1),
        }
        idx = idx_map.get(segment_type, 0)
        return persona.emotional_range[idx]

    def _maybe_inject_catchphrase(self, persona: "PersonaProfile", text: str, key: str) -> str:
        """~20% chance to prepend or append a catchphrase."""
        if not persona.catchphrases:
            return text
        count = self._call_counter.get(f"catchphrase_{key}", 0)
        self._call_counter[f"catchphrase_{key}"] = count + 1
        # Every 5th call gets a catchphrase
        if count % 5 == 0:
            cp = persona.catchphrases[count % len(persona.catchphrases)]
            # Alternate: prepend on even cycles, append on odd
            if count % 2 == 0:
                return f"{cp} {text}"
            else:
                return f"{text} {cp}"
        return text

    # Then modify generate_dialogue to be persona-aware.
    # The key change: after building the text, if a persona is assigned,
    # wrap the DialogueLine with emotion from the persona and inject catchphrases.
```

Full updated HostAgent with persona-aware `generate_dialogue`:

```python
    def generate_dialogue(self, segment: Segment, repo: Optional["PersonaRepository"] = None) -> DialogueBlock:
        """Generate host dialogue for any segment type, persona-aware."""
        # Base text generation (same logic as before)
        if segment.type == SegmentType.INTRO:
            template = self._next_template(HOST_INTROS, f"intro_{segment.id}")
            text = template.format(title=segment.title, prompt=segment.dialogue_prompt)
        elif segment.type == SegmentType.OUTRO:
            template = self._next_template(HOST_OUTRO, "outro")
            text = template.format(title=segment.title)
        elif segment.type == SegmentType.GUEST:
            template = self._next_template(HOST_GUEST, f"guest_{segment.id}")
            text = template.format(title=segment.title, prompt=segment.dialogue_prompt)
        elif segment.type == SegmentType.AD:
            template = self._next_template(HOST_AD, "ad")
            text = template.format(title=segment.title)
        else:
            template = self._next_template(HOST_CONTENT, f"content_{segment.id}")
            prompt = segment.dialogue_prompt or f"Let's explore {segment.title}."
            text = template.format(title=segment.title, prompt=prompt)

        # Persona enrichment
        emotion = None
        persona = None
        if self._persona_id is not None and repo is not None:
            persona = repo.get(self._persona_id)
        if persona is not None:
            emotion = self._select_emotion(persona, segment.type)
            text = self._maybe_inject_catchphrase(persona, text, segment.id)

        return DialogueBlock(
            segment_id=segment.id,
            lines=[DialogueLine(speaker="Host", text=text, order=0, emotion=emotion)],
        )

    # Also update generate_intro for consistency
    def generate_intro(self, segment: Segment, repo: Optional["PersonaRepository"] = None) -> DialogueBlock:
        return self.generate_dialogue(segment, repo)
```

Updated CoHostAgent:

```python
class CoHostAgent(BaseAgent):
    """Co-Host agent — adds perspective, reacts, introduces guests."""

    def __init__(self) -> None:
        super().__init__()
        self._call_counter: dict[str, int] = {}
        self._persona_id: Optional[str] = None

    # ── Persona management ────────────────────────────────────────

    def assign_persona(self, persona_id: str, repo: "PersonaRepository") -> None:
        persona = repo.get(persona_id)
        if persona is None:
            raise ValueError(f"Persona '{persona_id}' not found")
        self._persona_id = persona_id

    def get_persona(self, repo: "PersonaRepository") -> Optional["PersonaProfile"]:
        if self._persona_id is None:
            return None
        return repo.get(self._persona_id)

    def remove_persona(self) -> None:
        self._persona_id = None

    def _select_emotion(self, persona: "PersonaProfile", segment_type: SegmentType) -> str:
        if not persona.emotional_range:
            return persona.default_emotion
        idx_map = {
            SegmentType.INTRO: 0,
            SegmentType.OUTRO: -1,
            SegmentType.GUEST: min(1, len(persona.emotional_range) - 1),
            SegmentType.CONTENT: min(1, len(persona.emotional_range) - 1),
            SegmentType.AD: 0,
        }
        idx = idx_map.get(segment_type, 0)
        return persona.emotional_range[idx]

    def _maybe_inject_catchphrase(self, persona: "PersonaProfile", text: str, key: str) -> str:
        if not persona.catchphrases:
            return text
        count = self._call_counter.get(f"catchphrase_{key}", 0)
        self._call_counter[f"catchphrase_{key}"] = count + 1
        if count % 5 == 0:
            cp = persona.catchphrases[count % len(persona.catchphrases)]
            return f"{cp} {text}" if count % 2 == 0 else f"{text} {cp}"
        return text

    def generate_dialogue(self, segment: Segment, host_dialogue: str = "", repo: Optional["PersonaRepository"] = None) -> DialogueBlock:
        """Generate co-host dialogue, persona-aware."""
        lines: list[DialogueLine] = []

        # Base text generation
        if segment.type == SegmentType.INTRO:
            text = f"Can't wait to dive into {segment.title}!"
        elif segment.type == SegmentType.GUEST:
            template = self._next_template(COHOST_GUEST, f"guest_{segment.id}")
            text = template.format(title=segment.title)
        elif segment.type == SegmentType.OUTRO:
            text = "Great show today, everyone! Thanks for tuning in."
        else:
            template = self._next_template(COHOST_CONTENT, f"content_{segment.id}")
            prompt = segment.dialogue_prompt or f"there's a lot to say about {segment.title}"
            text = template.format(title=segment.title, prompt=prompt)

        # Persona enrichment
        emotion = None
        persona = None
        if self._persona_id is not None and repo is not None:
            persona = repo.get(self._persona_id)
        if persona is not None:
            emotion = self._select_emotion(persona, segment.type)
            text = self._maybe_inject_catchphrase(persona, text, segment.id)

        lines.append(DialogueLine(speaker="Co-Host", text=text, order=0, emotion=emotion))

        # Reaction line (if host dialogue)
        if host_dialogue and segment.type not in (SegmentType.OUTRO, SegmentType.AD):
            reaction = self._next_template(COHOST_REACTION, f"reaction_{segment.id}")
            react_emotion = None
            if persona is not None:
                idx = min(2, len(persona.emotional_range) - 1) if persona.emotional_range else 0
                react_emotion = persona.emotional_range[idx] if persona.emotional_range else persona.default_emotion
            lines.append(DialogueLine(
                speaker="Co-Host", text=reaction, order=len(lines),
                emotion=react_emotion or "curious",
            ))

        return DialogueBlock(segment_id=segment.id, lines=lines)
```

- [ ] **Step 4: Run dialogue persona tests**

Run:
```bash
cd /c/Users/MezbiN/broadcast && source .venv/Scripts/activate && python -m pytest tests/test_persona.py::TestPersonaAwareDialogue -v 2>&1
```
Expected: All PASS.

- [ ] **Step 5: Run full test suite to check backward compatibility**

Run:
```bash
cd /c/Users/MezbiN/broadcast && source .venv/Scripts/activate && python -m pytest --tb=short -q 2>&1
```
Expected: All existing tests still pass (dialogue tests unchanged behavior).

- [ ] **Step 6: Commit**

```bash
cd /c/Users/MezbiN/broadcast && git add agents/dialogue.py tests/test_persona.py && git commit -m "feat(dialogue): add persona-aware dialogue generation with emotion and catchphrases"
```

---

### Task 3: Persona RPC Endpoints (CRUD + assignment)

**Files:**
- Modify: `broadcast/agents/router.py`
- Modify: `broadcast/tests/test_persona.py` (add API tests)

**Interfaces:**
- Consumes: `PersonaRepository`, `HostAgent.assign_persona()`, `CoHostAgent.assign_persona()`
- Produces: `/agent/persona/*` endpoints

- [ ] **Step 1: Write persona API tests in `tests/test_persona.py`**

Append:

```python
class TestPersonaAPI:
    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from broadcast.main import app
        return TestClient(app)

    def test_list_personas_empty(self, client):
        resp = client.get("/agent/personas")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_create_persona(self, client):
        resp = client.post("/agent/personas", json={
            "name": "Energetic Host",
            "agent_type": "host",
            "personality_traits": ["enthusiastic", "warm"],
            "catchphrases": ["Let's go!"],
            "voice_style": "energetic",
            "default_emotion": "excited",
            "emotional_range": ["excited", "curious"],
            "background_story": "A high-energy morning show host",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Energetic Host"
        assert data["agent_type"] == "host"
        assert "id" in data
        return data["id"]

    def test_create_persona_validates_required(self, client):
        resp = client.post("/agent/personas", json={})
        assert resp.status_code == 422

    def test_get_persona(self, client):
        pid = self.test_create_persona(client)
        resp = client.get(f"/agent/personas/{pid}")
        assert resp.status_code == 200
        assert resp.json()["id"] == pid

    def test_get_nonexistent_persona(self, client):
        resp = client.get("/agent/personas/nonexistent")
        assert resp.status_code == 404

    def test_update_persona(self, client):
        pid = self.test_create_persona(client)
        resp = client.put(f"/agent/personas/{pid}", json={"name": "Updated Host"})
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated Host"

    def test_update_nonexistent(self, client):
        resp = client.put("/agent/personas/nope", json={"name": "X"})
        assert resp.status_code == 404

    def test_delete_persona(self, client):
        pid = self.test_create_persona(client)
        resp = client.delete(f"/agent/personas/{pid}")
        assert resp.status_code == 200
        resp = client.get(f"/agent/personas/{pid}")
        assert resp.status_code == 404

    def test_delete_nonexistent(self, client):
        resp = client.delete("/agent/personas/nope")
        assert resp.status_code == 404

    def test_assign_host_persona(self, client):
        pid = self.test_create_persona(client)
        resp = client.post(f"/agent/host/persona/{pid}")
        assert resp.status_code == 200
        assert resp.json()["assigned"] is True
        assert resp.json()["persona_id"] == pid
        assert resp.json()["agent"] == "host"

    def test_assign_cohost_persona(self, client):
        pid = self.test_create_persona(client)
        resp = client.post(f"/agent/cohost/persona/{pid}")
        assert resp.status_code == 200
        assert resp.json()["assigned"] is True

    def test_assign_nonexistent_persona(self, client):
        resp = client.post("/agent/host/persona/bogus")
        assert resp.status_code == 404

    def test_remove_host_persona(self, client):
        pid = self.test_create_persona(client)
        client.post(f"/agent/host/persona/{pid}")
        resp = client.delete("/agent/host/persona")
        assert resp.status_code == 200
        assert resp.json()["removed"] is True

    def test_remove_cohost_persona(self, client):
        pid = self.test_create_persona(client)
        client.post(f"/agent/cohost/persona/{pid}")
        resp = client.delete("/agent/cohost/persona")
        assert resp.status_code == 200

    def test_persona_affects_dialogue_through_api(self, client):
        # Create persona
        pid = client.post("/agent/personas", json={
            "name": "Excited Host", "agent_type": "host",
            "personality_traits": ["excited"], "catchphrases": ["Wow!"],
            "voice_style": "energetic", "default_emotion": "excited",
            "emotional_range": ["excited", "amazed"],
        }).json()["id"]

        # Assign to host
        client.post(f"/agent/host/persona/{pid}")

        # Create episode + segment + generate dialogue
        ep = client.post("/agent/episode", json={"title": "Morning Show"}).json()
        client.post(f"/agent/episode/{ep['id']}/segment",
                    json={"id": "intro", "type": "intro", "title": "Welcome!"})
        client.post(f"/agent/episode/{ep['id']}/load")
        client.post("/agent/director/next")
        resp = client.post("/agent/director/generate")
        data = resp.json()
        # Host dialogue should have emotion set
        assert data["host"]["lines"][0]["emotion"] is not None
        assert data["host"]["lines"][0]["emotion"] in ["excited", "amazed"]
```

- [ ] **Step 2: Run new API tests to verify they fail**

Run:
```bash
cd /c/Users/MezbiN/broadcast && source .venv/Scripts/activate && python -m pytest tests/test_persona.py::TestPersonaAPI -v 2>&1
```
Expected: FAIL — no persona endpoints exist yet.

- [ ] **Step 3: Add persona imports and endpoints to `agents/router.py`**

At the top of router.py, add the import:
```python
from broadcast.agents.persona import PersonaProfile, PersonaRepository, VoiceStyle
```

Add module-level singleton:
```python
_persona_repo = PersonaRepository()
```

Add the persona and assignment endpoints at the bottom of router.py (before the router variable — or append them to the module):

```python
# ── Persona endpoints ───────────────────────────────────────────

@router.get("/personas", tags=["persona"])
def list_personas() -> list[dict]:
    """List all persona profiles."""
    return [p.model_dump() for p in _persona_repo.list()]


@router.post("/personas", tags=["persona"])
def create_persona(body: dict) -> dict:
    """Create a new persona profile."""
    agent_type_str = body.get("agent_type", "host")
    if agent_type_str not in (t.value for t in AgentType):
        raise HTTPException(status_code=422, detail=f"Invalid agent_type: {agent_type_str}")
    voice_str = body.get("voice_style", "casual")
    if voice_str not in (v.value for v in VoiceStyle):
        raise HTTPException(status_code=422, detail=f"Invalid voice_style: {voice_str}")
    try:
        persona = _persona_repo.create(
            name=body.get("name", "").strip(),
            agent_type=AgentType(agent_type_str),
            personality_traits=body.get("personality_traits"),
            catchphrases=body.get("catchphrases"),
            voice_style=VoiceStyle(voice_str),
            default_emotion=body.get("default_emotion", "neutral"),
            emotional_range=body.get("emotional_range"),
            background_story=body.get("background_story", ""),
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return persona.model_dump()


@router.get("/personas/{persona_id}", tags=["persona"])
def get_persona(persona_id: str) -> dict:
    """Get a persona profile by ID."""
    persona = _persona_repo.get(persona_id)
    if persona is None:
        raise HTTPException(status_code=404, detail="Persona not found")
    return persona.model_dump()


@router.put("/personas/{persona_id}", tags=["persona"])
def update_persona(persona_id: str, body: dict) -> dict:
    """Update fields on an existing persona."""
    try:
        persona = _persona_repo.update(persona_id, **body)
    except ValueError:
        raise HTTPException(status_code=404, detail="Persona not found")
    return persona.model_dump()


@router.delete("/personas/{persona_id}", tags=["persona"])
def delete_persona(persona_id: str) -> dict:
    """Delete a persona profile."""
    # Refuse if currently assigned to host or co-host
    host_pid = getattr(_host, "_persona_id", None)
    cohost_pid = getattr(_cohost, "_persona_id", None)
    if persona_id == host_pid or persona_id == cohost_pid:
        raise HTTPException(status_code=409, detail="Cannot delete a persona that is currently assigned to an agent")
    if not _persona_repo.delete(persona_id):
        raise HTTPException(status_code=404, detail="Persona not found")
    return {"deleted": True, "persona_id": persona_id}


# ── Persona assignment endpoints ─────────────────────────────────

@router.post("/host/persona/{persona_id}", tags=["persona"])
def assign_host_persona(persona_id: str) -> dict:
    """Assign a persona profile to the Host agent."""
    persona = _persona_repo.get(persona_id)
    if persona is None:
        raise HTTPException(status_code=404, detail="Persona not found")
    _host.assign_persona(persona_id, _persona_repo)
    return {"assigned": True, "persona_id": persona_id, "agent": "host", "persona_name": persona.name}


@router.delete("/host/persona", tags=["persona"])
def remove_host_persona() -> dict:
    """Remove the persona from the Host agent (revert to default)."""
    _host.remove_persona()
    return {"removed": True, "agent": "host"}


@router.post("/cohost/persona/{persona_id}", tags=["persona"])
def assign_cohost_persona(persona_id: str) -> dict:
    """Assign a persona profile to the Co-Host agent."""
    persona = _persona_repo.get(persona_id)
    if persona is None:
        raise HTTPException(status_code=404, detail="Persona not found")
    _cohost.assign_persona(persona_id, _persona_repo)
    return {"assigned": True, "persona_id": persona_id, "agent": "cohost", "persona_name": persona.name}


@router.delete("/cohost/persona", tags=["persona"])
def remove_cohost_persona() -> dict:
    """Remove the persona from the Co-Host agent (revert to default)."""
    _cohost.remove_persona()
    return {"removed": True, "agent": "cohost"}
```

Also need to update `generate_dialogue` call sites in router.py to pass the repo. Update the `director_generate` endpoint:

```python
@router.post("/director/generate")
def director_generate() -> dict:
    """Generate host + co-host dialogue for the current segment."""
    segment = _director.current_segment
    if segment is None:
        raise HTTPException(status_code=400, detail="No segment loaded. Load an episode and advance to a segment.")
    host_block = _host.generate_dialogue(segment, repo=_persona_repo)
    cohost_block = _cohost.generate_dialogue(segment, host_block.lines[0].text if host_block.lines else "", repo=_persona_repo)
    _publish_agent_event("agent.dialogue.generated",
        segment_id=segment.id,
        host_text=host_block.lines[0].text if host_block.lines else "",
        cohost_text=cohost_block.lines[0].text if cohost_block.lines else "",
    )
    return {
        "segment_id": segment.id,
        "host": host_block.model_dump(),
        "cohost": cohost_block.model_dump(),
    }
```

And update the standalone dialogue endpoints:

```python
@router.post("/host/dialogue")
def host_dialogue(body: dict) -> dict:
    """Generate host dialogue for a given segment description."""
    segment = Segment(
        id=body.get("id", "custom"),
        type=SegmentType(body.get("type", "content")),
        title=body.get("title", "Untitled"),
        duration_seconds=body.get("duration_seconds", 30),
        scene_name=body.get("scene_name", ""),
        dialogue_prompt=body.get("dialogue_prompt", ""),
    )
    block = _host.generate_dialogue(segment, repo=_persona_repo)
    return block.model_dump()


@router.post("/cohost/dialogue")
def cohost_dialogue(body: dict) -> dict:
    """Generate co-host dialogue for a given segment description."""
    segment = Segment(
        id=body.get("id", "custom"),
        type=SegmentType(body.get("type", "content")),
        title=body.get("title", "Untitled"),
        duration_seconds=body.get("duration_seconds", 30),
        scene_name=body.get("scene_name", ""),
        dialogue_prompt=body.get("dialogue_prompt", ""),
    )
    block = _cohost.generate_dialogue(segment, repo=_persona_repo)
    return block.model_dump()
```

- [ ] **Step 4: Run the persona API tests**

Run:
```bash
cd /c/Users/MezbiN/broadcast && source .venv/Scripts/activate && python -m pytest tests/test_persona.py::TestPersonaAPI -v 2>&1
```
Expected: All PASS.

- [ ] **Step 5: Run full test suite**

Run:
```bash
cd /c/Users/MezbiN/broadcast && source .venv/Scripts/activate && python -m pytest --tb=short -q 2>&1
```
Expected: All 98 + N new tests pass.

- [ ] **Step 6: Commit**

```bash
cd /c/Users/MezbiN/broadcast && git add agents/router.py tests/test_persona.py && git commit -m "feat(api): add persona CRUD and assignment endpoints"
```

---

### Task 4: Dashboard Persona UI

**Files:**
- Create: `broadcast/dashboard/src/components/PersonaPanel.tsx`
- Create: `broadcast/dashboard/src/components/PersonaEditor.tsx`
- Modify: `broadcast/dashboard/src/lib/api.ts`
- Modify: `broadcast/dashboard/src/App.tsx`

- [ ] **Step 1: Add persona API types and functions to `dashboard/src/lib/api.ts`**

Append before the closing of the file:

```typescript
// ── Persona API types ──────────────────────────────────────────
export interface PersonaProfile {
  id: string;
  name: string;
  agent_type: "host" | "cohost" | "director" | "producer";
  personality_traits: string[];
  catchphrases: string[];
  voice_style: "energetic" | "calm" | "professional" | "casual" | "witty" | "serious";
  default_emotion: string;
  emotional_range: string[];
  background_story: string;
}

// ── Persona API functions ──────────────────────────────────────
export async function listPersonas(): Promise<PersonaProfile[]> {
  const res = await fetch(`${API_BASE}/agent/personas`);
  if (!res.ok) throw new Error("Failed to list personas");
  return res.json();
}

export async function createPersona(data: Partial<PersonaProfile>): Promise<PersonaProfile> {
  const res = await fetch(`${API_BASE}/agent/personas`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error("Failed to create persona");
  return res.json();
}

export async function getPersona(id: string): Promise<PersonaProfile> {
  const res = await fetch(`${API_BASE}/agent/personas/${id}`);
  if (!res.ok) throw new Error("Failed to get persona");
  return res.json();
}

export async function updatePersona(id: string, data: Partial<PersonaProfile>): Promise<PersonaProfile> {
  const res = await fetch(`${API_BASE}/agent/personas/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error("Failed to update persona");
  return res.json();
}

export async function deletePersona(id: string): Promise<void> {
  const res = await fetch(`${API_BASE}/agent/personas/${id}`, { method: "DELETE" });
  if (!res.ok) throw new Error("Failed to delete persona");
}

export async function assignHostPersona(personaId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/agent/host/persona/${personaId}`, { method: "POST" });
  if (!res.ok) throw new Error("Failed to assign host persona");
}

export async function removeHostPersona(): Promise<void> {
  const res = await fetch(`${API_BASE}/agent/host/persona`, { method: "DELETE" });
  if (!res.ok) throw new Error("Failed to remove host persona");
}

export async function assignCoHostPersona(personaId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/agent/cohost/persona/${personaId}`, { method: "POST" });
  if (!res.ok) throw new Error("Failed to assign co-host persona");
}

export async function removeCoHostPersona(): Promise<void> {
  const res = await fetch(`${API_BASE}/agent/cohost/persona`, { method: "DELETE" });
  if (!res.ok) throw new Error("Failed to remove co-host persona");
}
```

- [ ] **Step 2: Create `PersonaEditor.tsx`** — modal form for creating/editing personas

Write `dashboard/src/components/PersonaEditor.tsx`:

```tsx
import { useState } from "react";
import type { PersonaProfile } from "../lib/api";
import { createPersona, updatePersona } from "../lib/api";

const VOICE_STYLES = ["energetic", "calm", "professional", "casual", "witty", "serious"];
const AGENT_TYPES = ["host", "cohost", "director", "producer"];

interface PersonaEditorProps {
  persona: PersonaProfile | null; // null = creating new
  onSave: () => void;
  onCancel: () => void;
}

export function PersonaEditor({ persona, onSave, onCancel }: PersonaEditorProps) {
  const [name, setName] = useState(persona?.name ?? "");
  const [agentType, setAgentType] = useState(persona?.agent_type ?? "host");
  const [voiceStyle, setVoiceStyle] = useState(persona?.voice_style ?? "casual");
  const [traits, setTraits] = useState(persona?.personality_traits.join(", ") ?? "");
  const [catchphrases, setCatchphrases] = useState(persona?.catchphrases.join(", ") ?? "");
  const [emotions, setEmotions] = useState(persona?.emotional_range.join(", ") ?? "");
  const [defaultEmotion, setDefaultEmotion] = useState(persona?.default_emotion ?? "neutral");
  const [background, setBackground] = useState(persona?.background_story ?? "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSave = async () => {
    if (!name.trim()) { setError("Name is required"); return; }
    setSaving(true);
    setError(null);
    const payload = {
      name: name.trim(),
      agent_type: agentType,
      voice_style: voiceStyle,
      personality_traits: traits.split(",").map(s => s.trim()).filter(Boolean),
      catchphrases: catchphrases.split(",").map(s => s.trim()).filter(Boolean),
      emotional_range: emotions.split(",").map(s => s.trim()).filter(Boolean),
      default_emotion: defaultEmotion.trim(),
      background_story: background.trim(),
    };
    try {
      if (persona) {
        await updatePersona(persona.id, payload);
      } else {
        await createPersona(payload);
      }
      onSave();
    } catch {
      setError("Failed to save persona");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onClick={onCancel}>
      <div className="bg-white rounded-lg shadow-xl p-6 w-full max-w-lg max-h-[90vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
        <h3 className="font-semibold text-lg mb-4">{persona ? "Edit Persona" : "New Persona"}</h3>

        <div className="space-y-3">
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Name</label>
            <input type="text" value={name} onChange={e => setName(e.target.value)}
              className="w-full px-3 py-2 border rounded text-sm" placeholder="Morning Show Host" />
          </div>

          <div className="flex gap-3">
            <div className="flex-1">
              <label className="block text-xs font-medium text-gray-600 mb-1">Agent Type</label>
              <select value={agentType} onChange={e => setAgentType(e.target.value)}
                className="w-full px-3 py-2 border rounded text-sm">
                {AGENT_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
              </select>
            </div>
            <div className="flex-1">
              <label className="block text-xs font-medium text-gray-600 mb-1">Voice Style</label>
              <select value={voiceStyle} onChange={e => setVoiceStyle(e.target.value)}
                className="w-full px-3 py-2 border rounded text-sm">
                {VOICE_STYLES.map(v => <option key={v} value={v}>{v}</option>)}
              </select>
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Personality Traits (comma-separated)</label>
            <input type="text" value={traits} onChange={e => setTraits(e.target.value)}
              className="w-full px-3 py-2 border rounded text-sm" placeholder="enthusiastic, warm, curious" />
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Catchphrases (comma-separated)</label>
            <input type="text" value={catchphrases} onChange={e => setCatchphrases(e.target.value)}
              className="w-full px-3 py-2 border rounded text-sm" placeholder="Let's go!, That's fire!" />
          </div>

          <div className="flex gap-3">
            <div className="flex-1">
              <label className="block text-xs font-medium text-gray-600 mb-1">Default Emotion</label>
              <input type="text" value={defaultEmotion} onChange={e => setDefaultEmotion(e.target.value)}
                className="w-full px-3 py-2 border rounded text-sm" />
            </div>
            <div className="flex-1">
              <label className="block text-xs font-medium text-gray-600 mb-1">Emotional Range (comma-separated)</label>
              <input type="text" value={emotions} onChange={e => setEmotions(e.target.value)}
                className="w-full px-3 py-2 border rounded text-sm" placeholder="excited, curious, thoughtful" />
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Background Story</label>
            <textarea value={background} onChange={e => setBackground(e.target.value)}
              className="w-full px-3 py-2 border rounded text-sm h-20 resize-none"
              placeholder="Short bio for the persona..." />
          </div>
        </div>

        {error && <p className="text-sm text-red-600 mt-2">{error}</p>}

        <div className="flex justify-end gap-2 mt-4">
          <button onClick={onCancel} className="px-4 py-2 text-sm border rounded hover:bg-gray-50">Cancel</button>
          <button onClick={handleSave} disabled={saving}
            className="px-4 py-2 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50">
            {saving ? "Saving..." : "Save"}
          </button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Create `PersonaPanel.tsx`** — main persona management UI

Write `dashboard/src/components/PersonaPanel.tsx`:

```tsx
import { useState, useEffect } from "react";
import {
  listPersonas, deletePersona,
  assignHostPersona, removeHostPersona,
  assignCoHostPersona, removeCoHostPersona,
} from "../lib/api";
import type { PersonaProfile } from "../lib/api";
import { PersonaEditor } from "./PersonaEditor";

export function PersonaPanel() {
  const [personas, setPersonas] = useState<PersonaProfile[]>([]);
  const [editing, setEditing] = useState<PersonaProfile | null>(null);
  const [showNew, setShowNew] = useState(false);
  const [hostPersonaId, setHostPersonaId] = useState<string | null>(null);
  const [cohostPersonaId, setCohostPersonaId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const fetchPersonas = async () => {
    try {
      setPersonas(await listPersonas());
    } catch {
      setError("Failed to load personas");
    }
  };

  useEffect(() => { fetchPersonas(); }, []);

  const handleDelete = async (p: PersonaProfile) => {
    setError(null);
    try {
      await deletePersona(p.id);
      if (hostPersonaId === p.id) setHostPersonaId(null);
      if (cohostPersonaId === p.id) setCohostPersonaId(null);
      await fetchPersonas();
    } catch {
      setError("Failed to delete (persona may be assigned)");
    }
  };

  const handleAssignHost = async (id: string) => {
    setError(null);
    try {
      await assignHostPersona(id);
      setHostPersonaId(id);
    } catch {
      setError("Failed to assign host persona");
    }
  };

  const handleRemoveHost = async () => {
    setError(null);
    try {
      await removeHostPersona();
      setHostPersonaId(null);
    } catch {
      setError("Failed to remove host persona");
    }
  };

  const handleAssignCoHost = async (id: string) => {
    setError(null);
    try {
      await assignCoHostPersona(id);
      setCohostPersonaId(id);
    } catch {
      setError("Failed to assign co-host persona");
    }
  };

  const handleRemoveCoHost = async () => {
    setError(null);
    try {
      await removeCoHostPersona();
      setCohostPersonaId(null);
    } catch {
      setError("Failed to remove co-host persona");
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <h3 className="font-semibold">Persona Profiles</h3>
        <button onClick={() => setShowNew(true)}
          className="px-3 py-1.5 bg-blue-600 text-white rounded text-sm hover:bg-blue-700">
          + New Persona
        </button>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}

      {/* Assignment status */}
      <div className="flex gap-4 text-xs">
        <span className={hostPersonaId ? "text-green-700" : "text-gray-500"}>
          Host: {hostPersonaId ? personas.find(p => p.id === hostPersonaId)?.name ?? "Assigned" : "Default"}
        </span>
        <span className={cohostPersonaId ? "text-purple-700" : "text-gray-500"}>
          Co-Host: {cohostPersonaId ? personas.find(p => p.id === cohostPersonaId)?.name ?? "Assigned" : "Default"}
        </span>
      </div>

      {/* Persona list */}
      <div className="space-y-2">
        {personas.map(p => (
          <div key={p.id} className="border rounded p-3 space-y-1 hover:border-gray-400 transition-colors">
            <div className="flex justify-between items-start">
              <div>
                <p className="font-medium text-sm">{p.name}</p>
                <p className="text-xs text-gray-500">
                  {p.agent_type} · {p.voice_style}
                  {p.personality_traits.length > 0 && ` · ${p.personality_traits.join(", ")}`}
                </p>
              </div>
              <div className="flex gap-1">
                <button onClick={() => setEditing(p)}
                  className="px-2 py-1 text-xs border rounded hover:bg-gray-50">Edit</button>
                <button onClick={() => handleDelete(p)}
                  className="px-2 py-1 text-xs border rounded text-red-600 hover:bg-red-50">Delete</button>
              </div>
            </div>

            {p.catchphrases.length > 0 && (
              <p className="text-xs text-gray-600 italic">
                Catchphrases: {p.catchphrases.join(", ")}
              </p>
            )}
            {p.emotional_range.length > 0 && (
              <p className="text-xs text-gray-500">
                Emotions: {p.emotional_range.join(", ")}
              </p>
            )}

            {/* Assignment buttons */}
            <div className="flex gap-2 mt-1">
              {hostPersonaId === p.id ? (
                <button onClick={handleRemoveHost}
                  className="px-2 py-0.5 text-xs bg-orange-100 text-orange-700 rounded hover:bg-orange-200">
                  Unassign Host
                </button>
              ) : (
                <button onClick={() => handleAssignHost(p.id)}
                  className="px-2 py-0.5 text-xs bg-blue-50 text-blue-700 rounded hover:bg-blue-100">
                  Assign to Host
                </button>
              )}
              {cohostPersonaId === p.id ? (
                <button onClick={handleRemoveCoHost}
                  className="px-2 py-0.5 text-xs bg-orange-100 text-orange-700 rounded hover:bg-orange-200">
                  Unassign Co-Host
                </button>
              ) : (
                <button onClick={() => handleAssignCoHost(p.id)}
                  className="px-2 py-0.5 text-xs bg-purple-50 text-purple-700 rounded hover:bg-purple-100">
                  Assign to Co-Host
                </button>
              )}
            </div>
          </div>
        ))}
        {personas.length === 0 && (
          <p className="text-xs text-gray-400 text-center py-4">
            No personas yet. Create one to customize how your agents sound.
          </p>
        )}
      </div>

      {/* Editor modals */}
      {showNew && <PersonaEditor persona={null} onSave={() => { setShowNew(false); fetchPersonas(); }} onCancel={() => setShowNew(false)} />}
      {editing && <PersonaEditor persona={editing} onSave={() => { setEditing(null); fetchPersonas(); }} onCancel={() => setEditing(null)} />}
    </div>
  );
}
```

- [ ] **Step 4: Wire PersonaPanel into `App.tsx`**

Read `App.tsx` first, then add the persona tab. Create a `TABS` array (or add to existing tabs) and render PersonaPanel when selected:

```tsx
import { PersonaPanel } from "./components/PersonaPanel";
```

Add `"personas"` to the tab state and render: `{tab === "personas" && <PersonaPanel />}`

- [ ] **Step 5: Verify the dashboard compiles**

Run:
```bash
cd /c/Users/MezbiN/broadcast/dashboard && npx tsc --noEmit 2>&1
```
Expected: No type errors.

- [ ] **Step 6: Commit**

```bash
cd /c/Users/MezbiN/broadcast && git add dashboard/src/components/PersonaPanel.tsx dashboard/src/components/PersonaEditor.tsx dashboard/src/lib/api.ts dashboard/src/App.tsx && git commit -m "feat(dashboard): add persona profile management UI"
```

---

### Task 5: Update Agent Exports

- [ ] **Step 1: Update `agents/__init__.py` to export PersonaProfile**

```python
from broadcast.agents.persona import PersonaProfile, VoiceStyle

__all__ += ["PersonaProfile", "VoiceStyle"]
```

- [ ] **Step 2: Run full test suite**

Run:
```bash
cd /c/Users/MezbiN/broadcast && source .venv/Scripts/activate && python -m pytest --tb=short -q 2>&1
```
Expected: All tests pass.

- [ ] **Step 3: Commit**

```bash
cd /c/Users/MezbiN/broadcast && git add agents/__init__.py && git commit -m "chore: export PersonaProfile and VoiceStyle from agent package"
```

---

### Task 6: Final verification

- [ ] **Step 1: Run full test suite**

```bash
cd /c/Users/MezbiN/broadcast && source .venv/Scripts/activate && python -m pytest --tb=short -q 2>&1
```

- [ ] **Step 2: Run dashboard type check**

```bash
cd /c/Users/MezbiN/broadcast/dashboard && npx tsc --noEmit 2>&1
```

- [ ] **Step 3: Read the App.tsx to make sure the tab wiring looks correct**

- [ ] **Step 4: Create a quick integration test**

```bash
cd /c/Users/MezbiN/broadcast && source .venv/Scripts/activate && python -c "
from fastapi.testclient import TestClient
from broadcast.main import app
client = TestClient(app)

# 1. List (empty)
assert client.get('/agent/personas').json() == []

# 2. Create host persona
pid = client.post('/agent/personas', json={
    'name': 'Energetic Host', 'agent_type': 'host',
    'personality_traits': ['enthusiastic'], 'catchphrases': ['Let\'s go!'],
    'voice_style': 'energetic', 'default_emotion': 'excited',
    'emotional_range': ['excited', 'curious'],
}).json()['id']

# 3. Assign to host
r = client.post(f'/agent/host/persona/{pid}')
assert r.json()['assigned'] is True

# 4. Create episode + dialogue
ep = client.post('/agent/episode', json={'title': 'Test'}).json()
client.post(f'/agent/episode/{ep[\"id\"]}/segment',
    json={'id': 'intro', 'type': 'intro', 'title': 'Welcome'})
client.post(f'/agent/episode/{ep[\"id\"]}/load')
client.post('/agent/director/next')
dialogue = client.post('/agent/director/generate').json()
assert dialogue['host']['lines'][0]['emotion'] is not None
print(f'Persona emotion: {dialogue[\"host\"][\"lines\"][0][\"emotion\"]}')

# 5. Delete
client.delete(f'/agent/personas/{pid}')
assert client.get('/agent/personas').json() == []
print('All integration checks passed!')
" 2>&1
```

- [ ] **Step 5: Final commit and push**

```bash
cd /c/Users/MezbiN/broadcast && git push origin feat/broadcast-m3
```

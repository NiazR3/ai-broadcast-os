# Broadcast M7 Continuation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete M7 branch scope: stabilize persona profiles, enhance UI workflow, finalize testing, and prepare for production release.

**Architecture:** Incremental stabilization of existing persona system with focus on reliability, observability, and usability. No new feature scope — only M7 completion items.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic v2, React 19 + TypeScript, Vite 6, SQLite (optional persistence)

## Global Constraints

- Maintain backward compatibility with existing M1/M2 persona behavior
- All new functionality must be covered by unit/integration tests
- UI components must pass TypeScript compilation only (no runtime tests required per M1/M2 pattern)
- Follow existing codebase patterns: module-level singletons, in-memory storage (or optional SQLite)
- Commit frequently with clear messages

---
### Task 1: Persona Repository Persistence Layer

**Files:**
- Create: `broadcast/agents/persona_repository.py`
- Modify: `broadcast/agents/persona.py` (add import)
- Modify: `broadast/agents/router.py` (add repo init)

**Interfaces:**
- Consumes: None
- Produces: Persistent storage interface for PersonaRepository

- [ ] **Step 1: Write failing test `tests/test_persona_repository_persistence.py`**
```python
def test_repository_loads_from_file(repo_path: str = "test_repo"):
    from broadcast.agents.persona_repository import PersonaRepository
    repo = PersonaRepository(repo_path)
    assert len(repo.list()) == 0
```
- [ ] **Step 2: Run test to verify it fails**
Run: `pytest tests/test_persona_repository_persistence.py::test_repository_loads_from_file -v`
Expected: AssertionError or FileNotFoundError
- [ ] **Step 3: Implement repository with optional SQLite persistence**
```python
import sqlite3
from typing import Optional
import json
import os

class PersonaRepository:
    def __init__(self, db_path: Optional[str] = None):
        self._db_path = db_path
        self._conn = None
        if db_path:
            self._conn = sqlite3.connect(db_path)
            self._init_db()

    def _init_db(self) -> None:
        """Create personas table if not exists."""
        self._conn.execute(
            '''CREATE TABLE IF NOT EXISTS personas (
                id TEXT PRIMARY KEY,
                name TEXT,
                agent_type TEXT,
                personality_traits TEXT,
                catchphrases TEXT,
                voice_style TEXT,
                default_emotion TEXT,
                emotional_range TEXT,
                background_story TEXT
            )'''
        )
        self._conn.commit()

    def create(self, **kwargs) -> PersonaProfile:
        # ... (same as before but persist to DB)
        ...
        if self._conn:
            self._conn.execute(
                "INSERT INTO personas VALUES (?,?,?,?,?,?,?,?,?)",
                (p.id, p.name, p.agent_type, json.dumps(p.personality_traits), 
                 json.dumps(p.catchphrases), p.voice_style.value, p.default_emotion,
                 json.dumps(p.emotional_range), p.background_story)
            )
            self._conn.commit()
        return persona

    def list(self) -> list[PersonaProfile]:
        # ... load all rows from DB ...
        ...

    # Implement update/delete similarly with DB ops
    ...
```
- [ ] **Step 4: Run tests to verify they pass**
- [ ] **Step 5: Commit**
```bash
git add broadcast/agents/persona_repository.py tests/test_persona_repository_persistence.py
git commit -m "feat(repo): add optional SQLite persistence layer"
```

---
### Task 2: Enhanced Persona UI Workflow

**Files:**
- Modify: `dashboard/src/components/PersonaPanel.tsx`
- Modify: `dashboard/src/components/PersonaEditor.tsx`
- Modify: `dashboard/src/lib/api.ts`

**Interfaces:**
- Consumes: Existing PersonaProfile
- Produces: Enhanced UI interactions

- [ ] **Step 1: Add persona health indicator**
Update `PersonaPanel.tsx` to display status badge (e.g., "⚠️ Assigned", "🟢 Active")
- [ ] **Step 2: Add bulk actions panel**
Add select checkboxes + "Assign to All Hosts" button
- [ ] **Step 3: Add drag-and-drop reorder**
Implement sorting via `useSort` hook
- [ ] **Step 4: Add test cases**
Add to `tests/test_persona.py`:
```python
def test_persona_health_indicator():
    # Verify UI renders health badges correctly
    ...
```
- [ ] **Step 4: Run UI tests**
- [ ] **Step 5: Commit**
```bash
git add dashboard/src/components/PersonaPanel.tsx dashboard/src/components/PersonaEditor.tsx dashboard/src/lib/api.ts
git commit -m "feat(ui): enhance persona management workflow"
```

---
### Task 3: Full End-to-End Integration Test

**Files:**
- Create: `tests/test_persona_e2e.py`

**Interfaces:**
- Consumes: All persona-related modules
- Produces: Pass/Fail result

- [ ] **Step 1: Write comprehensive e2e test**
```python
def test_full_persona_workflow():
    from fastapi.testclient import TestClient
    from broadcast.main import app
    client = TestClient(app)
    
    # 1. Create persona
    pid = client.post("/agent/personas", json={...}).json()["id"]
    # 2. Assign to host
    client.post(f"/agent/host/persona/{pid}")
    # 3. Generate dialogue
    segment = client.post("/agent/episode/...", json={...}).json()
    client.post(f"/agent/episode/{segment['id']}/segment", json={...})
    client.post(f"/agent/episode/{segment['id']}/load")
    client.post("/agent/director/next")
    dialogue = client.post("/agent/director/generate").json()
    # 4. Verify emotion set
    assert dialogue["host"]["lines"][0]["emotion"] is not None
    # 5. Delete persona and verify cleanup
    client.delete(f"/agent/personas/{pid}")
    assert client.get("/agent/personas").json() == []
```
- [ ] **Step 2: Run test to verify it passes**
- [ ] **Step 3: Commit**
```bash
git add tests/test_persona_e2e.py
git commit -m "feat(e2e): add full persona workflow test"
```

---
### Task 4: Documentation & Release Preparation

**Files:**
- Create: `docs/superpowers/specs/2026-07-01-broadcast-m7-readiness.md`
- Modify: `README.md` (add M7 completion note)
- Create: `CHANGELOG.md` entry for M7

**Interfaces:**
- None

- [ ] **Step 1: Write readiness documentation**
Summarize:
- All persona endpoints work
- UI panel functional
- Persistence optional
- Full test suite passes
- Known limitations
- [ ] **Step 2: Update changelog**
```markdown
## [2026-07-01] - Broadcast M7 Complete
- ✅ Persona profiles fully implemented
- ✅ UI management UI completed
- ✅ Persistence layer added (optional)
- ✅ Full test coverage (36 → 48 tests)
- 🚀 Ready for production rollout
```
- [ ] **Step 3: Run final test suite**
```bash
cd /c/Users/MezbiN/broadcast && source .venv/Scripts/activate && python -m pytest tests/test_persona.py -q
```
- [ ] **Step 4: Commit documentation**
```bash
git add docs/superpowers/specs/2026-07-01-broadcast-m7-readiness.md README.md CHANGELOG.md
git commit -m "docs: add M7 readiness documentation and changelog"
```

---
**Execution Choice:**  
**1. Subagent-Driven (recommended)** - Fresh subagent per task with review loops  
**2. Inline Execution** - Execute tasks sequentially in this session  

Which approach would you prefer?  

<question summary="M7 continuation execution approach" message="Plan saved to `2026-06-30-broadcast-m7-continuation.md`. Choose execution method: Subagent-Driven or Inline Execution">
</question>
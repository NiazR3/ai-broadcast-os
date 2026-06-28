# M3: Persona Profiles — Design Spec

## Overview
Persona profiles define the personality, catchphrases, vocal style, and emotional range
of each broadcast agent (Host, Co-Host, etc.). They decouple "who is speaking" from
"how they say it," allowing operators to customize agent personalities without touching
dialogue templates or agent code.

## Models

```python
class VoiceStyle(str, Enum):
    ENERGETIC = "energetic"
    CALM = "calm"
    PROFESSIONAL = "professional"
    CASUAL = "casual"
    WITTY = "witty"
    SERIOUS = "serious"

class PersonaProfile(BaseModel):
    id: str                       # uuid hex
    name: str                     # "Morning Show Host", "Tech Co-Host"
    agent_type: AgentType         # maps to host / cohost / director / producer
    personality_traits: list[str] # ["enthusiastic", "curious", "sarcastic"]
    catchphrases: list[str]       # ["Let's dive in!", "That's fire!"]
    voice_style: VoiceStyle       # overall delivery style
    default_emotion: str          # "excited" — fallback for dialogue
    emotional_range: list[str]    # ["excited", "serious", "thoughtful", "surprised"]
    background_story: str = ""    # short bio context for LLM prompt building
```

## Repository
- In-memory `dict[str, PersonaProfile]` following `ProducerAgent._episodes` pattern.
- CRUD: create, get, list, update, delete.
- Assignment: host persona and co-host persona stored as optional IDs on the
  respective agent instances. Each agent holds `self.persona_id: Optional[str]`.
- Default personas: Host + Co-Host defaults created on first access if none exist.

## Persona-Aware Dialogue
- `HostAgent` and `CoHostAgent` gain `assign_persona(persona_id) -> None` and
  `get_persona() -> Optional[PersonaProfile]`.
- When a persona is assigned, dialogue generation:
  - Injects catchphrases into templates (sparingly — ~20% of lines get one).
  - Selects emotion from `emotional_range` based on segment type (intro → first
    emotion, content → middle, outro → last).
  - Tags `DialogueLine.emotion` with the selected emotion.
  - Cycles through `personality_traits` in the template selection weighting.
- No persona assigned → pure backward-compatible current behavior.

## API Endpoints
Prefix: `/agent/persona`

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/personas` | List all personas |
| POST | `/personas` | Create persona |
| GET | `/personas/{id}` | Get persona by ID |
| PUT | `/personas/{id}` | Update persona |
| DELETE | `/personas/{id}` | Delete persona (refuse if currently assigned) |
| POST | `/host/persona/{persona_id}` | Assign persona to Host |
| POST | `/cohost/persona/{persona_id}` | Assign persona to Co-Host |
| DELETE | `/host/persona` | Remove persona from Host (revert to default) |
| DELETE | `/cohost/persona` | Remove persona from Co-Host |

## Dashboard UI
- `PersonaPanel.tsx` component: list/create/edit/delete persona profiles.
- Assign/remove persona for host and co-host.
- Preview: show how current persona affects generated dialogue (emotion tags).

## Files to Create/Modify

### New files
- `broadcast/agents/persona.py` — PersonaProfile model, PersonaRepository
- `broadcast/tests/test_persona.py` — unit + integration tests
- `broadcast/dashboard/src/components/PersonaPanel.tsx` — persona UI
- `broadcast/dashboard/src/components/PersonaEditor.tsx` — create/edit form

### Modified files
- `broadcast/agents/dialogue.py` — persona awareness (assign, get, emotion selection)
- `broadcast/agents/router.py` — persona CRUD + assignment endpoints
- `broadcast/agents/__init__.py` — export PersonaProfile
- `broadcast/dashboard/src/lib/api.ts` — persona API functions + types
- `broadcast/dashboard/src/App.tsx` — wire PersonaPanel tab

## Testing Strategy
- Model unit tests: valid/invalid personas, voice_style enum, catchphrases length.
- Repository tests: CRUD operations, duplicate ID handling, listing.
- Dialogue persona tests: persona influences emotion tag, catchphrases appear,
  no persona = backward compatible.
- API integration tests: full CRUD lifecycle, assignment, delete-reject-when-assigned.
- Frontend: TypeScript compilation only (no component tests — same pattern as M1/M2).

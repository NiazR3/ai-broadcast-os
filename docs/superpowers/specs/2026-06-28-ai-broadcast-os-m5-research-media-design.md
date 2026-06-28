# M5: Research Agent + Media Agent — Design Specification

## Document Version
- **Version:** 1.0
- **Date:** 2026-06-28
- **Milestone:** M5 (Research Agent + Media Agent)
- **Prerequisites:** M1 (Core Streaming) ✓, M2 (Agent Framework) ✓, M3 (Persona Profiles) ✓, M4 (Audience) ✓

---

## 1. Overview

M5 adds two new agents to the broadcast system:

- **Research Agent** — submits fact-checking and topic research requests against a pluggable backend, providing the host/co-host with structured research results (summary, key points, source citations, fact checks).
- **Media Agent** — generates SVG-based visual assets (bar charts, line charts, pie charts, text overlays) that can be previewed in the dashboard and assigned to segments.

Both follow the established patterns: `BaseAgent` subclass, in-memory state, EventBus integration, REST API, and dashboard panels.

---

## 2. Architecture

```
                    ┌──────────────────────────────┐
                    │       DirectorAgent           │
                    │  (triggers research before    │
                    │   segments via EventBus)      │
                    └──────────┬───────────────────┘
                               │ EventBus: research.*
                               ▼
┌─────────────────────────────────────────────────┐
│               ResearchAgent                      │
│  ┌─────────────┐  ┌──────────────────────────┐  │
│  │ ResearchEng. │  │  MockResearchBackend     │  │
│  │ (queues,     │  │  (template results by    │  │
│  │  retrieves)  │  │   topic keyword)         │  │
│  └─────────────┘  └──────────────────────────┘  │
│  EventBus: research.topic.submitted             │
│  EventBus: research.result.ready                │
└──────────────────────┬──────────────────────────┘
                       │
         ┌─────────────┴─────────────┐
         ▼                           ▼
   REST API                     Dashboard
   /research/*                  ResearchPanel
```

```
                    ┌──────────────────────────────┐
                    │       DirectorAgent           │
                    │  (triggers asset generation   │
                    │   per segment type)           │
                    └──────────┬───────────────────┘
                               │ EventBus: media.*
                               ▼
┌─────────────────────────────────────────────────┐
│               MediaAgent                         │
│  ┌─────────────┐  ┌──────────────────────────┐  │
│  │ MediaEngine  │  │  ChartRenderer           │  │
│  │ (lifecycle)  │  │  (bar/line/pie SVG)     │  │
│  └─────────────┘  └──────────────────────────┘  │
│  EventBus: media.asset.created                  │
└──────────────────────┬──────────────────────────┘
                       │
         ┌─────────────┴─────────────┐
         ▼                           ▼
   REST API                     Dashboard
   /media/*                     MediaPanel
```

---

## 3. Research Agent

### 3.1 Models (`broadcast/research/models.py`)

```python
class ResearchStatus(str, Enum):
    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    COMPLETE = "complete"
    FAILED = "failed"

class ResearchTopic(BaseModel):
    id: str
    query: str
    segment_id: str = ""
    segment_title: str = ""
    context: str = ""
    status: ResearchStatus = ResearchStatus.QUEUED
    created_at: float = 0.0
    completed_at: Optional[float] = None

class SourceCitation(BaseModel):
    url: str
    title: str
    snippet: str
    relevance_score: float = 0.0

class FactCheck(BaseModel):
    claim: str
    verdict: str  # "supported" | "contradicted" | "unverified"
    explanation: str = ""

class ResearchResult(BaseModel):
    id: str
    topic_id: str
    summary: str
    key_points: list[str]
    sources: list[SourceCitation]
    fact_checks: list[FactCheck]
    created_at: float = 0.0
```

### 3.2 Research Engine (`broadcast/research/engine.py`)

**`ResearchBackend` (abstract):**
- `research(topic: ResearchTopic) -> ResearchResult` — perform research on a topic
- `supports_topic(topic: str) -> bool` — whether this backend can handle the topic

**`MockResearchBackend(ResearchBackend)`:**
- Returns template-based results keyed to topic keywords
- Built-in topic coverage: technology, weather, sports, entertainment, science, health, business, politics, general
- Non-matching topics return a polite "no research available" result
- `RESEARCH_TEMPLATES` dict with ~10 topic categories, each having summary, 3 key points, 2 sources, 1 fact check

**`ResearchEngine`:**
- `submit(topic: ResearchTopic, backend: ResearchBackend) -> str` — queues and immediately resolves (sync mock) or schedules async
- `get(topic_id: str) -> Optional[ResearchResult]`
- `list(limit: int = 10) -> list[ResearchResult]`
- `extract_topics(text: str) -> list[str]` — simple keyword extraction from segment text
- Stores results in `dict[str, ResearchResult]` (in-memory)

**`ResearchAgent(BaseAgent)`:**
- Subscribes to EventBus for `director.segment_started` events
- Auto-extracts topics from segment titles/prompts and submits research
- Publishes `research.result.ready` on EventBus when results are available
- `get_context_for_segment(segment_id: str) -> Optional[str]` — formatted summary for dialogue injection

### 3.3 REST API

| Method | Path | Description |
|--------|------|-------------|
| POST | `/research/submit` | Submit topic for research |
| GET | `/research/results` | List past results |
| GET | `/research/results/{id}` | Get specific result |
| POST | `/research/extract` | Extract topics from text |

### 3.4 Dashboard Panel (`ResearchPanel.tsx`)
- Submit topics via text input + "Research" button
- Results displayed as cards: summary, key points (bullets), sources (clickable), fact checks (verdict badges)
- History list of past results with search filtering
- Auto-research toggle (enable/disable automatic extraction from segments)

---

## 4. Media Agent

### 4.1 Models (`broadcast/media/models.py`)

```python
class ChartType(str, Enum):
    BAR = "bar"
    LINE = "line"
    PIE = "pie"

class AssetType(str, Enum):
    CHART = "chart"
    TEXT_OVERLAY = "text_overlay"

class AssetStatus(str, Enum):
    GENERATED = "generated"
    ASSIGNED = "assigned"
    DELETED = "deleted"

class ChartConfig(BaseModel):
    chart_type: ChartType
    title: str = ""
    labels: list[str]
    datasets: list[dict]  # [{"label": "Series 1", "values": [10, 20, 30]}]
    width: int = 600
    height: int = 400
    colors: list[str] = ["#3B82F6", "#10B981", "#F59E0B", "#EF4444", "#8B5CF6"]

class TextOverlayConfig(BaseModel):
    text: str
    font_size: int = 48
    color: str = "#FFFFFF"
    background_color: str = "transparent"
    width: int = 800
    height: int = 200

class MediaAsset(BaseModel):
    id: str
    type: AssetType
    segment_id: str = ""
    svg_content: str
    metadata: dict = {}
    status: AssetStatus = AssetStatus.GENERATED
    created_at: float = 0.0
```

### 4.2 Media Engine (`broadcast/media/engine.py`)

**`ChartRenderer`:**
- `render_bar(config: ChartConfig) -> str` — SVG bar chart with axis labels, gridlines, legend
- `render_line(config: ChartConfig) -> str` — SVG line chart with data points, axis, legend
- `render_pie(config: ChartConfig) -> str` — SVG pie/donut chart with segment labels
- `render_text_overlay(config: TextOverlayConfig) -> str` — SVG text with optional background rect

SVG generation is pure string templating — no external chart library dependency.

**`MediaEngine`:**
- `generate_chart(config: ChartConfig) -> MediaAsset` — creates SVG via ChartRenderer
- `generate_text_overlay(config: TextOverlayConfig) -> MediaAsset` — creates SVG text overlay
- `get(asset_id: str) -> Optional[MediaAsset]`
- `list(segment_id: str = "", type: Optional[AssetType] = None) -> list[MediaAsset]`
- `delete(asset_id: str) -> bool`
- `assign_to_segment(asset_id: str, segment_id: str) -> bool`
- All assets stored in `dict[str, MediaAsset]` (in-memory)

**`MediaAgent(BaseAgent)`:**
- Provides facade over MediaEngine (follows BaseAgent pattern)
- Publishes `media.asset.created` on EventBus
- No auto-generation (director or user triggers explicitly)

### 4.3 REST API

| Method | Path | Description |
|--------|------|-------------|
| POST | `/media/chart` | Generate a chart (bar/line/pie) |
| POST | `/media/text` | Generate a text overlay |
| GET | `/media/assets` | List assets (query: segment_id, type) |
| GET | `/media/assets/{id}` | Get asset with SVG content |
| DELETE | `/media/assets/{id}` | Delete asset |
| POST | `/media/assets/{id}/assign` | Assign to segment |

### 4.4 Dashboard Panel (`MediaPanel.tsx`)
- **Create chart tab:** Select type (bar/line/pie) → enter title, labels, series values → pick colors → preview rendered SVG → save
- **Create text tab:** Enter text, set font size/color, preview → save
- **Asset gallery:** Grid of generated assets with SVG thumbnails, filter by type, delete, assign to segment
- SVG preview rendered directly in the browser (no external viewer needed)

---

## 5. Integration Points

| Component | Research Agent | Media Agent |
|-----------|---------------|-------------|
| EventBus | Publishes `research.topic.submitted`, `research.result.ready` | Publishes `media.asset.created` |
| DirectorAgent | (future) auto-submit research before segments | (future) auto-generate assets per segment type |
| HostAgent | (future) inject research context into dialogue prompts | — |
| OBS | — | (future) SVG → PNG → OBS scene source |
| Dashboard | ResearchPanel with submit/view/history | MediaPanel with chart builder + gallery |

---

## 6. Files

### Create
```
broadcast/research/__init__.py
broadcast/research/models.py
broadcast/research/engine.py            — ResearchEngine + ResearchBackend + MockResearchBackend
broadcast/research/router.py
broadcast/media/__init__.py
broadcast/media/models.py
broadcast/media/engine.py              — MediaEngine + ChartRenderer
broadcast/media/router.py
broadcast/tests/test_research.py
broadcast/tests/test_media.py
broadcast/dashboard/src/components/ResearchPanel.tsx
broadcast/dashboard/src/components/MediaPanel.tsx
```

### Modify
```
broadcast/main.py                       — include research + media routers
broadcast/dashboard/src/lib/api.ts      — add types + API functions
broadcast/dashboard/src/App.tsx         — add ResearchPanel + MediaPanel sections
```

---

## 7. Testing

### `tests/test_research.py` (~20 tests)
- Model validation (ResearchTopic, ResearchResult, SourceCitation, FactCheck)
- MockResearchBackend returns correct templates per keyword
- Fallback for unknown topics
- ResearchEngine: submit, get, list, extract_topics
- ResearchAgent lifecycle (start/stop)
- API endpoints: submit, list, get, extract

### `tests/test_media.py` (~25 tests)
- Model validation (ChartConfig, MediaAsset, TextOverlayConfig)
- ChartRenderer: bar chart SVG structure (axes, labels, bars, legend)
- ChartRenderer: line chart SVG structure (data points, lines, axis)
- ChartRenderer: pie chart SVG structure (segments, labels)
- ChartRenderer: text overlay SVG structure
- ChartRenderer: invalid config (empty labels, mismatched data)
- MediaEngine: generate, get, list, delete, assign
- MediaAgent lifecycle (start/stop)
- API endpoints: create chart, create text, list, get, delete, assign

**Target:** 45+ new tests.

---

## 8. Decisions & Trade-offs

| Decision | Rationale |
|----------|-----------|
| **Mock research backend** (no LangChain) | Pluggable interface ready for real integration. Template-based results are predictable and testable. |
| **Pure SVG generation** (no D3.js/Puppeteer) | No external rendering deps. SVGs are strings — easy to store, serve, preview, and later composite. |
| **Sync mock research** (no async queue yet) | Mock backend returns instantly. Async queue can be added when a real search backend is plugged in. |
| **Separate research + media modules** | They're independent domains. Separate modules are easier to understand, test, and extend independently. |
| **In-memory asset storage** | Matches all prior M1-M4 patterns. SVG strings are small (2-10 KB each). Cap at 100 assets prevents bloat. |

---

## 9. Approval

- **Design Approved** ✔️ (by stakeholder)
- **Next:** Write implementation plan → begin development

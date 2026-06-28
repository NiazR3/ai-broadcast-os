# M6: Full Analytics Suite — Design Specification

> **Version:** 1.0
> **Date:** 2026-06-28

## 1. Overview

Build a comprehensive analytics suite for AI Broadcast OS that tracks broadcast sessions, collects real-time metrics, and generates post-stream reports. Uses SQLite for persistence (upgradable to ClickHouse/Postgres later), the existing EventBus for live event ingestion, and new React dashboard panels for visualization.

## 2. Architecture

```
EventBus (broadcast.*, audience.*, media.* events)
    │
    ▼
MetricsCollector ────► SQLite (metrics_snapshots, event_log)
SessionManager   ────► SQLite (broadcast_sessions)
ReportGenerator  ────► SQLite → dict / CSV
    │
    ▼
REST API (/analytics/*) ◄──► React Dashboard (AnalyticsPanel)
```

| Component | Responsibility |
|-----------|---------------|
| **AnalyticsDatabase** | SQLite wrapper, WAL mode, auto-create tables, parameterized queries |
| **MetricsCollector** | EventBus subscriber, routes events → snapshots + event log |
| **SessionManager** | Broadcast session lifecycle (create/update/close) |
| **ReportGenerator** | Post-stream report builder (dict + CSV export) |
| **AnalyticsAgent** | BaseAgent subclass, owns database + collector lifecycle |
| **REST API** | 6 endpoints under `/analytics/` |
| **AnalyticsPanel** | React dashboard component (live metrics, history, reports) |

## 3. Data Models

### 3.1 BroadcastSession
```python
class BroadcastSession(BaseModel):
    id: str
    started_at: float
    ended_at: float | None = None
    duration_seconds: float = 0.0
    peak_viewers: int = 0
    avg_viewers: float = 0.0
    total_chat_messages: int = 0
    unique_chatters: int = 0
    platforms: list[str] = []
    status: str = "live"  # "live" | "ended"
```

### 3.2 MetricsSnapshot
```python
class MetricsSnapshot(BaseModel):
    id: str
    session_id: str
    timestamp: float
    viewer_count: int = 0
    chat_rate: float = 0.0  # messages/min
    platform: str = "all"
```

### 3.3 AnalyticsEvent
```python
class AnalyticsEvent(BaseModel):
    id: str
    session_id: str
    timestamp: float
    event_type: str
    payload: dict = {}
```

### 3.4 AnalyticsReport
```python
class AnalyticsReport(BaseModel):
    session_id: str
    summary: ReportSummary
    engagement: EngagementMetrics
    timeline: list[AnalyticsEvent]
    generated_at: float
```

### 3.5 ReportSummary / EngagementMetrics
```python
class ReportSummary(BaseModel):
    duration_seconds: float
    peak_viewers: int
    avg_viewers: float
    platforms: list[str]
    status: str

class EngagementMetrics(BaseModel):
    total_chat_messages: int
    unique_chatters: int
    messages_per_minute: float
    top_chatters: list[dict]
    polls_conducted: int = 0
    assets_created: int = 0
```

## 4. Database Schema

Single SQLite file at `broadcast_data/analytics.db`:

```sql
CREATE TABLE IF NOT EXISTS broadcast_sessions (
    id TEXT PRIMARY KEY,
    started_at REAL NOT NULL,
    ended_at REAL,
    duration_seconds REAL DEFAULT 0,
    peak_viewers INTEGER DEFAULT 0,
    avg_viewers REAL DEFAULT 0,
    total_chat_messages INTEGER DEFAULT 0,
    unique_chatters INTEGER DEFAULT 0,
    platforms TEXT DEFAULT '[]',  -- JSON array
    status TEXT DEFAULT 'live'
);

CREATE TABLE IF NOT EXISTS metrics_snapshots (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    timestamp REAL NOT NULL,
    viewer_count INTEGER DEFAULT 0,
    chat_rate REAL DEFAULT 0,
    platform TEXT DEFAULT 'all',
    FOREIGN KEY (session_id) REFERENCES broadcast_sessions(id)
);

CREATE TABLE IF NOT EXISTS event_log (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    timestamp REAL NOT NULL,
    event_type TEXT NOT NULL,
    payload TEXT DEFAULT '{}',  -- JSON blob
    FOREIGN KEY (session_id) REFERENCES broadcast_sessions(id)
);

CREATE INDEX IF NOT EXISTS idx_snapshots_session ON metrics_snapshots(session_id);
CREATE INDEX IF NOT EXISTS idx_events_session ON event_log(session_id);
CREATE INDEX IF NOT EXISTS idx_events_type ON event_log(event_type);
```

## 5. Data Flow

### 5.1 Broadcast Start
1. User starts broadcast → API calls `/broadcast/start`
2. EventBus publishes `broadcast.started`
3. `MetricsCollector` receives event → `SessionManager.create_session()`
4. New `BroadcastSession` row inserted into SQLite

### 5.2 During Broadcast (every ~10s)
1. `MetricsCollector` timer fires → snapshots current metrics
2. `MetricsSnapshot` row inserted into SQLite
3. New live metrics pushed via existing WebSocket (`/broadcast/ws`)
4. Any significant event (scene switch, poll, chat milestone) → `AnalyticsEvent` row inserted

### 5.3 Broadcast Stop
1. User stops broadcast → API calls `/broadcast/stop`
2. EventBus publishes `broadcast.stopped`
3. `SessionManager.close_session()` computes aggregates from snapshots + event log
4. `BroadcastSession` updated with `status="ended"`, `peak_viewers`, `avg_viewers`, etc.
5. Final metrics push via WebSocket

### 5.4 Post-Stream Report
1. `GET /analytics/sessions/{id}/report` → `ReportGenerator.build_report(id)`
2. Queries session row + aggregations from snapshots + event log
3. Returns `AnalyticsReport` as JSON
4. `GET /analytics/sessions/{id}/report.csv` returns CSV of metrics snapshots

## 6. MetricsCollector Design

- Implements `start()`/`stop()` following the BaseAgent pattern
- On `start()`: subscribes to EventBus channels (`broadcast`, `audience`, `media`)
- Maintains a running 60-second rolling window for chat rate computation
- Periodically (10s interval) writes a MetricsSnapshot while a session is active
- Routes events:
  - `broadcast.started` → session created
  - `broadcast.stopped` → session closed with aggregates
  - `broadcast.*` platform events → platform list updated
  - `audience.chat.message` → message count + unique chatters updated
  - `scene.switched`, `audience.poll.*`, `media.asset.created` → event log entries

## 7. SessionManager

- `create_session(platforms, timestamp)` → returns BroadcastSession
- `close_session(session_id)` → computes aggregates, marks as ended
- `get_active_session()` → returns current live session or None
- `list_sessions(limit=20)` → returns recent sessions
- `get_session(session_id)` → returns single session

## 8. ReportGenerator

- `build_report(session_id)` → queries SQLite aggregates, returns AnalyticsReport
- `build_csv(session_id)` → queries metrics_snapshots, returns CSV string
- Aggregate computations:
  - `peak_viewers`: MAX(viewer_count) from snapshots
  - `avg_viewers`: AVG(viewer_count) from snapshots
  - `total_chat_messages`: COUNT from event_log WHERE event_type = 'audience.chat.message'
  - `unique_chatters`: DISTINCT count from event_log payload
  - `top_chatters`: TOP 5 from event_log grouped by user
  - `polls_conducted`: COUNT from event_log WHERE event_type LIKE 'audience.poll.%'
  - `assets_created`: COUNT from event_log WHERE event_type = 'media.asset.created'

## 9. REST API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/analytics/sessions` | List all broadcast sessions (query: limit, status) |
| GET | `/analytics/sessions/{id}` | Single session detail |
| GET | `/analytics/sessions/{id}/report` | Post-stream report (JSON) |
| GET | `/analytics/sessions/{id}/report.csv` | CSV download of metrics |
| GET | `/analytics/live` | Current live session metrics |
| GET | `/analytics/dashboard` | Aggregated dashboard data (latest sessions, live status, totals) |

All endpoints protected by `Depends(verify_api_key)`.

## 10. Dashboard (AnalyticsPanel.tsx)

React component with three sections:

1. **Live Metrics** — shown when broadcast is active:
   - Viewer count (current, peak, average)
   - Chat rate (messages/min)
   - Uptime counter
   - Auto-refreshes every 5s via polling (or WebSocket when connected)

2. **Session History** — table of past broadcasts:
   - Date, duration, peak viewers, total chat messages
   - Click a row to view full report
   - CSV download button per session

3. **Report Viewer** — detail view for a selected session:
   - Summary card (duration, peak/avg viewers, platforms)
   - Engagement card (messages, chatters, top chatters, polls, assets)
   - Event timeline (chronological list of events during broadcast)

Follows existing Tailwind patterns: `white rounded-lg shadow-sm p-6` sections.

## 11. Testing

- **Unit tests:** Models, AnalyticsDatabase, MetricsCollector (with mock EventBus), SessionManager, ReportGenerator
- **API tests:** All 6 endpoints via TestClient with auth header
- **Integration:** End-to-end broadcast lifecycle → metrics collected → report generated
- SQLite tests use `:memory:` database for isolation
- No external dependencies (all in-memory + SQLite)

## 12. File Structure

```
broadcast/
  analytics/
    __init__.py
    models.py          # Pydantic models + enums
    database.py        # AnalyticsDatabase (SQLite wrapper)
    collector.py       # MetricsCollector (EventBus subscriber)
    session.py         # SessionManager
    reporting.py       # ReportGenerator (JSON + CSV)
    agent.py           # AnalyticsAgent (BaseAgent subclass)
    router.py          # REST API endpoints
  tests/
    test_analytics.py  # 25+ tests
  dashboard/
    src/
      components/
        AnalyticsPanel.tsx   # Main analytics dashboard component
      lib/
        api.ts               # + analytics API functions
```

## 13. YAGNI Exclusions

Explicitly **not** included in M6:
- External time-series databases (ClickHouse, InfluxDB) — SQLite is sufficient at this scale
- Kafka or external message queues — EventBus handles in-process pub/sub
- Grafana or Prometheus integration — custom React panels instead
- Real WebSocket push from backend (reuses existing `/broadcast/ws`) — polling is sufficient
- PDF report generation — CSV is lighter and immediately useful
- Historical trend analysis (compare across sessions) — data is collected but analysis deferred

---

## Self-Review Checklist

- [x] No placeholders ("TBD", "TODO")
- [x] Internal consistency — architecture matches component descriptions
- [x] Scope appropriate for a single implementation plan
- [x] No ambiguity — each component has a clear responsibility
- [x] Follows existing codebase patterns (BaseAgent, EventBus, APIRouter, dashboard)
- [x] YAGNI applied — exclusions explicitly listed

# M4: Audience Interaction & Moderation — Design Specification

## Document Version
- **Version:** 1.0
- **Date:** 2026-06-28
- **Milestone:** M4 (Audience Interaction & Moderation)
- **Prerequisites:** M1 (Core Streaming Engine) ✓, M2 (Agent Framework) ✓, M3 (Persona Profiles) ✓

---

## 1. Overview

M4 adds audience-facing features to the AI Broadcast OS: chat ingestion, moderation, polls, and an audience agent that bridges chat activity into the broadcast loop. This enables the host/co-host to reference live chat, run polls, and moderate messages — all without platform API tokens (mock chat for development, real connectors plug in later).

---

## 2. Scope

### In Scope
- **Chat model & repository** — `ChatMessage`, `ChatUser`, ring-buffer storage
- **MockChatBridge** — simulated chat at configurable rate (9 persona types, varied messages)
- **ModerationEngine** — keyword blocklist + per-user rate-limit + spam heuristics (caps/emoji/repeat/URL flood) + placeholder for ML
- **PollEngine** — create, vote (one per user), auto-close, tally
- **AudienceAgent** — subscribes to audience events, provides chat context for the broadcast loop
- **REST API** — full CRUD for chat, moderation rules, polls, stats
- **Dashboard UI** — live chat feed, moderation actions, poll management
- **EventBus integration** — all audience events published to `audience.*` channels, forwarded via existing WebSocket
- **Tests** — unit + integration, following existing patterns

### Out of Scope (M5+)
- Real platform chat connectors (Twitch PubSub, YouTube Live Chat API) — require OAuth tokens
- ML-based toxicity classifier (engine has a placeholder hook)
- Virtual callers / simulated audience participants
- Chat-driven segment transitions

---

## 3. Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  MockChatBridge │────▶│  ChatRepository  │────▶│  EventBus       │
│  (simulated)    │     │  (ring buffer)   │     │  audience.*     │
└─────────────────┘     └────────┬─────────┘     └────────┬────────┘
                                 │                        │
                                 ▼                        ▼
                        ┌──────────────────┐     ┌─────────────────┐
                        │ ModerationEngine │     │  PollEngine     │
                        │  (rules pipeline)│     │  (create/vote)  │
                        └──────────────────┘     └────────┬────────┘
                                 │                        │
                                 ▼                        ▼
                        ┌──────────────────────────────────────────┐
                        │           AudienceAgent                  │
                        │  (subscribes, aggregates, serves API)     │
                        └──────────────────────────────────────────┘
                                        │
                                        ▼
                        ┌──────────────────────────────────────────┐
                        │      REST API + WebSocket                │
                        │  (/audience/* + existing /broadcast/ws)  │
                        └──────────────────────────────────────────┘
                                        │
                                        ▼
                        ┌──────────────────────────────────────────┐
                        │      Dashboard UI                        │
                        │  (ChatPanel + PollPanel)                  │
                        └──────────────────────────────────────────┘
```

### Data Flow
1. **Chat ingestion** — MockChatBridge generates messages → pushed through ModerationEngine → clean messages stored in ChatRepository → published to EventBus (`audience.chat.message`)
2. **Moderation** — flagged messages published to `audience.moderation.flagged`; moderator actions published to `audience.moderation.actioned`
3. **Polls** — created via API or AudienceAgent → users vote via API → closed automatically (or manually) → results published to `audience.poll.*`
4. **AudienceAgent** — subscribes to all `audience.*` events, provides `get_recent_chat()`, `get_poll_results()`, `get_activity_summary()` for dialogue integration
5. **WebSocket** — existing `/broadcast/ws` forwards all `audience.*` events to dashboard

---

## 4. Component Design

### 4.1 Models (`broadcast/audience/models.py`)

```python
class ChatPlatform(str, Enum):
    TWITCH = "twitch"
    YOUTUBE = "youtube"
    FACEBOOK = "facebook"
    MOCK = "mock"

class ChatUserRole(str, Enum):
    VIEWER = "viewer"
    MODERATOR = "moderator"
    BROADCASTER = "broadcaster"
    VIP = "vip"

class ChatUser(BaseModel):
    id: str
    display_name: str
    platform: ChatPlatform
    role: ChatUserRole = ChatUserRole.VIEWER
    badges: list[str] = []

class ChatMessage(BaseModel):
    id: str
    platform: ChatPlatform
    user: ChatUser
    text: str
    timestamp: float
    moderated: bool = False
    moderation_action: Optional[str] = None

class ModerationAction(str, Enum):
    FLAG = "flag"
    APPROVE = "approve"
    TIMEOUT = "timeout"
    BAN = "ban"

class ModerationRule(BaseModel):
    id: str
    pattern: str          # regex pattern
    action: ModerationAction
    reason: str
    enabled: bool = True
    created_at: float = 0.0

class PollStatus(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"
    CLOSED = "closed"

class PollOption(BaseModel):
    text: str
    votes: int = 0

class Poll(BaseModel):
    id: str
    question: str
    options: list[PollOption]
    status: PollStatus = PollStatus.PENDING
    duration_seconds: int = 60
    created_at: float = 0.0
    closed_at: Optional[float] = None

class PollVote(BaseModel):
    poll_id: str
    option_index: int
    user_id: str
    timestamp: float

class ChatActivity(BaseModel):
    total_messages: int = 0
    unique_users: int = 0
    messages_per_minute: float = 0.0
    top_chatters: list[dict] = []
```

### 4.2 Chat Ingestion (`broadcast/audience/chat.py`)

**`ChatBridge` (abstract base class):**
- `subscribe() -> AsyncIterator[ChatMessage]` — yields messages from a platform
- `start()` / `stop()` — lifecycle

**`MockChatBridge(ChatBridge)`:**
- Generates messages at configurable rate (default 1 per 3 seconds)
- Uses 9 distinct viewer personas with varied message types: greetings, questions, reactions, spam, emoji spam, links, caps lock, moderation tests, hype
- Configurable spam probability (default 10%) to test moderation
- `rate: float = 0.33` — messages per second

**`ChatRepository`:**
- In-memory ring buffer, capped at 500 messages
- `add(message: ChatMessage) -> None`
- `recent(limit: int = 50) -> list[ChatMessage]`
- `by_user(user_id: str) -> list[ChatMessage]`
- `flagged() -> list[ChatMessage]` — messages awaiting moderation
- `update_moderation(message_id: str, action: str) -> bool`

### 4.3 Moderation Engine (`broadcast/audience/moderation.py`)

**`ModerationEngine`:**
- Cascading filter pipeline, each rule checked in order:
  1. **Keyword blocklist** — regex patterns matched against message text
  2. **Per-user rate limit** — configurable messages/second threshold per user
  3. **Spam heuristics** — > 70% caps, > 50% emoji, repeated messages, URL flood
- `check(message: ChatMessage) -> Optional[ModerationAction]` — returns action or None (approve)
- `add_rule(rule: ModerationRule) -> None`
- `remove_rule(rule_id: str) -> bool`
- `list_rules() -> list[ModerationRule]`
- **Missed-flag detection:** every 20th approved message is spot-checked against rules (configurable confidence adjustment)
- **ML placeholder:** `_ml_classify(text: str) -> Optional[dict]` — returns None (stub for future BERT/classifier integration)

### 4.4 Poll Engine (`broadcast/audience/polls.py`)

**`PollEngine`:**
- `create_poll(question: str, options: list[str], duration_seconds: int) -> Poll`
- `vote(poll_id: str, option_index: int, user_id: str) -> PollVote` — one vote per user
- `close_poll(poll_id: str) -> Poll` — force close
- `get_active_poll() -> Optional[Poll]`
- `list_polls(include_closed: bool = False) -> list[Poll]`
- `get_results(poll_id: str) -> dict` — option vote counts + winner
- Auto-close: background check on each vote for expired polls
- Publishes events: `audience.poll.created`, `audience.poll.vote`, `audience.poll.closed`

### 4.5 Audience Agent (`broadcast/audience/agent.py`)

**`AudienceAgent(BaseAgent)`:**
- Subscribes to `audience.*` events on EventBus
- `get_recent_chat(count: int = 5) -> list[ChatMessage]` — latest messages
- `get_poll_results() -> Optional[dict]` — latest closed poll
- `get_activity_summary() -> ChatActivity` — aggregated stats
- `start_simulation() -> None` — begins mock chat generation
- `stop_simulation() -> None` — stops mock chat
- Integrates with dialogue in M5 (provides chat context to HostAgent)

---

## 5. REST API

All endpoints under `/audience/`, protected by `verify_api_key` dependency.

### Chat
| Method | Path | Description |
|--------|------|-------------|
| GET | `/audience/chat` | Recent messages (query: `limit`, `user_id`, `flagged`) |
| POST | `/audience/chat` | Inject a chat message (for testing) |
| POST | `/audience/chat/{id}/flag` | Flag a message |
| POST | `/audience/chat/{id}/moderate` | Apply moderation action |

### Moderation Rules
| Method | Path | Description |
|--------|------|-------------|
| GET | `/audience/moderation/rules` | List rules |
| POST | `/audience/moderation/rules` | Create rule |
| DELETE | `/audience/moderation/rules/{id}` | Delete rule |

### Polls
| Method | Path | Description |
|--------|------|-------------|
| GET | `/audience/polls` | List polls (query: `include_closed`) |
| POST | `/audience/polls` | Create poll |
| POST | `/audience/polls/{id}/vote` | Vote (body: `option_index`, `user_id`) |
| POST | `/audience/polls/{id}/close` | Force-close a poll |

### Stats
| Method | Path | Description |
|--------|------|-------------|
| GET | `/audience/stats` | Aggregated chat activity |

---

## 6. Dashboard UI

### ChatPanel.tsx
- **Live chat feed** — scrollable message list with user avatar (initial), name, text, timestamp
- **Moderation actions** — per-message buttons: Flag / Approve / Timeout / Ban
- **Flagged queue** — separate tab showing flagged messages awaiting action
- **Rule management** — inline list of active rules with add/remove controls

### PollPanel.tsx
- **Create poll** — question input + dynamic option fields (2-6 options) + duration slider
- **Active poll** — live vote display with progress bars, vote button per option
- **Poll history** — closed polls with final results

### Integration in App.tsx
- ChatPanel replaces or augments the Teleprompter section
- PollPanel added as a new section
- EventBus WebSocket integration for real-time updates

---

## 7. Files to Create / Modify

### Create
```
broadcast/audience/__init__.py
broadcast/audience/models.py
broadcast/audience/chat.py          — ChatBridge, MockChatBridge, ChatRepository
broadcast/audience/moderation.py     — ModerationEngine, ModerationRule
broadcast/audience/polls.py          — PollEngine, PollRepository
broadcast/audience/agent.py          — AudienceAgent
broadcast/audience/router.py         — REST API endpoints
broadcast/tests/test_audience.py     — All M4 tests
```

### Modify
```
broadcast/main.py                    — include audience router
broadcast/agents/__init__.py         — export AudienceAgent (optional)
broadcast/dashboard/src/App.tsx      — add ChatPanel + PollPanel sections
broadcast/dashboard/src/lib/api.ts   — add audience API types + functions
broadcast/dashboard/src/components/ChatPanel.tsx    — new
broadcast/dashboard/src/components/PollPanel.tsx     — new
```

No existing files need structural changes — the audience module is self-contained and plugs in via the router and EventBus.

---

## 8. Testing

### File: `tests/test_audience.py`

| Test Group | What it covers |
|------------|---------------|
| **Model validation** | ChatMessage, ChatUser, Poll, ModerationRule field constraints |
| **ChatRepository** | add, recent, by_user, flagged, ring buffer cap, moderation update |
| **MockChatBridge** | message generation, rate config, stream lifecycle |
| **ModerationEngine** | keyword block, rate limit, spam heuristics (caps/emoji/repeat/URL), rule CRUD, missed-flag detection |
| **PollEngine** | create, vote dedup, auto-close, tally, list history |
| **AudienceAgent** | start/stop lifecycle, EventBus subscription |
| **API endpoints** | Chat CRUD, moderation rules lifecycle, poll lifecycle, stats |
| **WebSocket** | audience events forwarded through existing WS endpoint |

**Target:** 60+ tests minimum (matching M3 density), all following existing `conftest.py` fixtures.

---

## 9. Integration Points

| Existing Component | Integration |
|-------------------|-------------|
| EventBus | Audience publishes `audience.*` events, existing broadcast WebSocket forwards them |
| BaseAgent | AudienceAgent extends BaseAgent, follows same lifecycle pattern |
| Router pattern | Follows `/agent/` and `/broadcast/` router pattern with `verify_api_key` |
| Module-level singletons | Same pattern as M2/M3 (`_producer`, `_director`, etc.) |
| Dashboard | New panels follow existing React 19 + Tailwind patterns, same `useWebSocket` hook |

---

## 10. Design Decisions & Trade-offs

| Decision | Rationale |
|----------|-----------|
| **In-memory ring buffer** (no Redis) | Matches existing M1-M3 pattern; avoids infrastructure dependency. Cache-friendly, fast, simple. Cap at 500 prevents unbounded memory. |
| **MockChatBridge** (no real platform APIs) | Real integrations need OAuth tokens and platform approval. Mock gives us testable, demoable module now. Platform connectors slot in via the same `ChatBridge` interface. |
| **Moderation as cascading rules** (not ML) | Rules engine is deterministic, testable, debuggable. ML placeholder for future upgrade keeps the interface stable. |
| **PollEngine with manual + auto-close** | Manual close for director control; auto-close for unattended operation. Both needed for real use. |
| **Separate test file** (not in test_agents.py) | M4 is a new domain (audience), not an agent extension. Follows M1's pattern of separate test files per domain. |

---

## 11. Approval

- **Design Approved** ✔️ (by stakeholder)
- **Next:** Write implementation plan using writing-plans skill → begin development on Task 1

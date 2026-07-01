"""Tests for the ShowRunnerAgent orchestrator.

Covers: production pipeline, run playback, state machine transitions,
error handling, persona/ poll/ research/ media integration, and API.
"""

from __future__ import annotations

import pytest

from broadcast.agents.models import AgentType, ScriptStatus
from broadcast.agents.persona import PersonaRepository, VoiceStyle
from broadcast.agents.show_runner import (
    SEGMENT_TEMPLATES,
    ShowRunnerAgent,
    ShowState,
    TOPIC_CHART_TEMPLATES,
    TOPIC_PERSONA_MAP,
)



# ── Fixtures ────────────────────────────────────────────────────────────


@pytest.fixture
def runner() -> ShowRunnerAgent:
    """Create a fresh ShowRunnerAgent with no shared state."""
    return ShowRunnerAgent()


@pytest.fixture
def seeded_runner() -> ShowRunnerAgent:
    """Create a runner with pre-seeded personas and a known producer."""
    repo = PersonaRepository()
    repo.create(
        id="host_tech",
        name="TechGuru",
        agent_type=AgentType.HOST,
        personality_traits=["analytical", "enthusiastic"],
        catchphrases=["Let's break it down!"],
        voice_style=VoiceStyle.WITTY,
        background_story="Technology expert and AI enthusiast",
    )
    repo.create(
        id="cohost_tech",
        name="DataSage",
        agent_type=AgentType.COHOST,
        personality_traits=["thoughtful", "curious"],
        catchphrases=["That's a great point!"],
        voice_style=VoiceStyle.PROFESSIONAL,
        background_story="Data analyst and science communicator",
    )
    return ShowRunnerAgent(persona_repo=repo)


# ── Initial state ──────────────────────────────────────────────────────


class TestShowRunnerInitialState:
    def test_default_state_is_idle(self, runner: ShowRunnerAgent) -> None:
        assert runner.state == ShowState.IDLE

    def test_agent_identity(self, runner: ShowRunnerAgent) -> None:
        assert runner.agent_name == "ShowRunner"
        assert runner.agent_type == "show_runner"

    def test_no_episode_on_init(self, runner: ShowRunnerAgent) -> None:
        assert runner.current_episode is None

    def test_get_status_idle(self, runner: ShowRunnerAgent) -> None:
        status = runner.get_show_status()
        assert status["state"] == "idle"
        assert status["episode"] is None
        assert status["dialogue_segments"] == []


# ── produce_show ──────────────────────────────────────────────────────


class TestProduceShow:
    def test_produces_episode_in_ready_state(self, runner: ShowRunnerAgent) -> None:
        result = runner.produce_show("The Future of AI", "technology")
        assert result["state"] == "ready"
        assert "episode_id" in result
        assert result["segments"] == 6
        assert result["topic"] == "The Future of AI"

    def test_produces_all_six_segments(self, runner: ShowRunnerAgent) -> None:
        result = runner.produce_show("Climate Change", "weather")
        assert result["segments"] == len(SEGMENT_TEMPLATES)

    def test_segments_have_dialogue_generated(self, runner: ShowRunnerAgent) -> None:
        result = runner.produce_show("AI Revolution", "technology")
        assert result["dialogue_generated"] == 6

    def test_generates_media_assets(self, runner: ShowRunnerAgent) -> None:
        result = runner.produce_show("Tech Trends", "technology")
        assert result["assets_created"] >= 3

    def test_creates_poll_for_known_category(self, runner: ShowRunnerAgent) -> None:
        result = runner.produce_show("Quantum Computing", "science")
        assert result["poll_id"] is not None

    def test_submits_research(self, runner: ShowRunnerAgent) -> None:
        result = runner.produce_show("Mars Colonization", "science")
        assert result["research_count"] >= 1

    def test_returns_production_log(self, runner: ShowRunnerAgent) -> None:
        result = runner.produce_show("Test Topic", "general")
        assert "production_log" in result
        assert len(result["production_log"]) > 0

    def test_returns_production_time(self, runner: ShowRunnerAgent) -> None:
        result = runner.produce_show("Quick Test")
        assert "production_time_seconds" in result
        assert result["production_time_seconds"] >= 0

    def test_requires_non_empty_topic(self, runner: ShowRunnerAgent) -> None:
        result = runner.produce_show("")
        assert "error" in result

    def test_refuses_produce_in_ready_state(self, runner: ShowRunnerAgent) -> None:
        runner.produce_show("First Show")
        result = runner.produce_show("Second Show")
        assert "error" in result

    def test_reset_allows_new_production(self, runner: ShowRunnerAgent) -> None:
        runner.produce_show("First Show")
        runner.reset()
        result = runner.produce_show("Second Show")
        assert result["state"] == "ready"

    def test_unknown_category_falls_back_gracefully(self, runner: ShowRunnerAgent) -> None:
        result = runner.produce_show("Custom Topic", "nonexistent_category")
        assert result["state"] == "ready"
        assert result["segments"] == 6

    def test_unknown_category_no_chart(self, runner: ShowRunnerAgent) -> None:
        result = runner.produce_show("Custom", "nonexistent")
        assert result["assets_created"] >= 3

    def test_produces_all_categories(self, runner: ShowRunnerAgent) -> None:
        for category in TOPIC_CHART_TEMPLATES:
            result = runner.produce_show(f"Topic for {category}", category)
            assert result["state"] == "ready", f"Failed for category '{category}'"
            runner.reset()

    def test_production_stores_episode(self, runner: ShowRunnerAgent) -> None:
        result = runner.produce_show("Persistent", "technology")
        assert runner.current_episode is not None
        assert runner.current_episode.id == result["episode_id"]
        assert runner.current_episode.status == ScriptStatus.READY

    def test_production_logs_assets(self, runner: ShowRunnerAgent) -> None:
        result = runner.produce_show("Asset Check", "technology")
        status = runner.get_show_status()
        assert len(status["assets"]) == result["assets_created"]

    def test_assigns_default_poll_for_unknown_category(self, runner: ShowRunnerAgent) -> None:
        result = runner.produce_show("Custom", "unknown_cat")
        assert result["poll_id"] is not None


# ── produce_show with seeded personas ──────────────────────────────────


class TestProduceShowWithPersonas:
    def test_assigns_host_persona(self, seeded_runner: ShowRunnerAgent) -> None:
        result = seeded_runner.produce_show("AI in Healthcare", "technology")
        assert result["personas"]["host"] is not None
        assert result["personas"]["cohost"] is not None

    def test_persona_appears_in_status(self, seeded_runner: ShowRunnerAgent) -> None:
        seeded_runner.produce_show("Deep Learning", "technology")
        status = seeded_runner.get_show_status()
        assert status["personas"]["host"] is not None
        assert status["personas"]["cohost"] is not None


# ── run_show ──────────────────────────────────────────────────────────


class TestRunShow:
    """Tests for run_show — all methods are async (await run_show())."""
    pytestmark = pytest.mark.asyncio

    async def test_run_after_produce_returns_completed(self, runner: ShowRunnerAgent) -> None:
        runner.produce_show("Run Test", "general")
        result = await runner.run_show()
        assert result["state"] == "completed"

    async def test_run_returns_segment_results(self, runner: ShowRunnerAgent) -> None:
        runner.produce_show("Segment Test", "technology")
        result = await runner.run_show()
        assert "segment_results" in result
        assert len(result["segment_results"]) == 6

    async def test_run_segments_have_dialogue(self, runner: ShowRunnerAgent) -> None:
        runner.produce_show("Dialogue Test", "technology")
        result = await runner.run_show()
        for seg in result["segment_results"]:
            assert "host_dialogue" in seg
            assert "cohost_dialogue" in seg
            assert len(seg["host_dialogue"]) > 0 or len(seg["cohost_dialogue"]) > 0

    async def test_run_segments_have_metadata(self, runner: ShowRunnerAgent) -> None:
        runner.produce_show("Metadata Test", "technology")
        result = await runner.run_show()
        for seg in result["segment_results"]:
            assert "segment_id" in seg
            assert "segment_type" in seg
            assert "scene" in seg
            assert "duration_seconds" in seg
            assert "order" in seg

    async def test_episode_status_during_run(self, runner: ShowRunnerAgent) -> None:
        runner.produce_show("Status Test", "technology")
        assert runner.current_episode is not None
        assert runner.current_episode.status == ScriptStatus.READY
        result = await runner.run_show()
        assert result["state"] == "completed"

    async def test_run_returns_run_log(self, runner: ShowRunnerAgent) -> None:
        runner.produce_show("Log Test", "technology")
        result = await runner.run_show()
        assert "run_log" in result
        assert len(result["run_log"]) > 0

    async def test_run_without_produce_returns_error(self, runner: ShowRunnerAgent) -> None:
        result = await runner.run_show()
        assert "error" in result

    async def test_run_with_wrong_episode_id(self, runner: ShowRunnerAgent) -> None:
        runner.produce_show("Episode Test", "technology")
        result = await runner.run_show(episode_id="nonexistent_id")
        assert "error" in result

    async def test_cannot_run_twice(self, runner: ShowRunnerAgent) -> None:
        runner.produce_show("Once", "technology")
        await runner.run_show()
        result = await runner.run_show()
        assert "error" in result

    async def test_state_progression(self, runner: ShowRunnerAgent) -> None:
        assert runner.state == ShowState.IDLE
        runner.produce_show("Progress", "technology")
        assert runner.state == ShowState.READY
        result = await runner.run_show()
        assert result["state"] == "completed"

    async def test_segment_order_in_results(self, runner: ShowRunnerAgent) -> None:
        runner.produce_show("Order", "technology")
        result = await runner.run_show()
        orders = [s["order"] for s in result["segment_results"]]
        assert orders == sorted(orders)


# ── reset ─────────────────────────────────────────────────────────────


class TestReset:

    def test_reset_clears_state(self, runner: ShowRunnerAgent) -> None:
        runner.produce_show("Resetable", "technology")
        runner.reset()
        assert runner.state == ShowState.IDLE
        assert runner.current_episode is None

    @pytest.mark.asyncio
    async def test_reset_allows_new_production_after_run(self, runner: ShowRunnerAgent) -> None:
        runner.produce_show("First")
        await runner.run_show()
        runner.reset()
        result = runner.produce_show("Second")
        assert result["state"] == "ready"

    def test_reset_clears_status_data(self, runner: ShowRunnerAgent) -> None:
        runner.produce_show("Clear", "technology")
        runner.reset()
        status = runner.get_show_status()
        assert status["episode"] is None
        assert status["dialogue_segments"] == []
        assert status["assets"] == []

    def test_reset_idempotent(self, runner: ShowRunnerAgent) -> None:
        runner.reset()
        assert runner.state == ShowState.IDLE
        runner.reset()
        assert runner.state == ShowState.IDLE


# ── Edge cases and error handling ─────────────────────────────────────


class TestEdgeCases:
    def test_produce_and_run_empty_topic_after_reset(self, runner: ShowRunnerAgent) -> None:
        runner.produce_show("Valid Topic")
        runner.reset()
        result = runner.produce_show("")
        assert "error" in result

    def test_produce_show_very_long_topic(self, runner: ShowRunnerAgent) -> None:
        long_topic = "X" * 500
        result = runner.produce_show(long_topic, "general")
        assert result["state"] == "ready"

    def test_produce_show_special_characters(self, runner: ShowRunnerAgent) -> None:
        result = runner.produce_show("AI & Machine Learning: The Future (2026)!", "technology")
        assert result["state"] == "ready"

    def test_concurrent_poll_creation(self, runner: ShowRunnerAgent) -> None:
        """Multiple productions should each create a different poll."""
        runner.produce_show("Test", "technology")
        poll_id1 = runner.get_show_status()["poll_id"]
        runner.reset()
        runner.produce_show("Test", "sports")
        poll_id2 = runner.get_show_status()["poll_id"]
        assert poll_id1 != poll_id2


# ── Segment template integrity ──────────────────────────────────────────


class TestSegmentIntegrity:
    def test_all_segment_ids_unique(self) -> None:
        ids = [t["id"] for t in SEGMENT_TEMPLATES]
        assert len(ids) == len(set(ids))

    def test_all_segment_types_valid(self) -> None:
        from broadcast.agents.models import SegmentType
        valid = {t.value for t in SegmentType}
        for tmpl in SEGMENT_TEMPLATES:
            assert tmpl["type"].value in valid

    def test_segment_order_is_sequential(self, runner: ShowRunnerAgent) -> None:
        runner.produce_show("Order", "general")
        ep = runner.current_episode
        assert ep is not None
        for i, seg in enumerate(ep.segments):
            assert seg.order == i


# ── Topic data integrity ──────────────────────────────────────────────


class TestTopicDataIntegrity:
    def test_all_persona_map_styles_valid(self) -> None:
        valid = {v.value for v in VoiceStyle}
        for host_style, cohost_style in TOPIC_PERSONA_MAP.values():
            assert host_style.value in valid
            assert cohost_style.value in valid

    def test_all_chart_templates_valid(self) -> None:
        from broadcast.media.models import ChartType
        valid_chart_types = {t.value for t in ChartType}
        for category, template in TOPIC_CHART_TEMPLATES.items():
            assert template["chart_type"].value in valid_chart_types
            assert len(template["labels"]) > 0
            assert len(template["datasets"]) > 0

    def test_poll_templates_have_min_options(self) -> None:
        from broadcast.agents.show_runner import POLL_TEMPLATES
        for question, options in POLL_TEMPLATES.values():
            assert len(question) > 0  # noqa: SIM300 - intentional non-bool check
            assert len(options) >= 2

    def test_default_poll_has_valid_structure(self) -> None:
        from broadcast.agents.show_runner import DEFAULT_POLL
        question, options = DEFAULT_POLL
        assert len(question) > 0
        assert len(options) >= 2


# ── Production summary structure ──────────────────────────────────────


class TestProductionStructure:
    def test_result_contains_all_keys(self, runner: ShowRunnerAgent) -> None:
        result = runner.produce_show("Structure", "technology")
        expected_keys = {
            "episode_id", "topic", "category", "state", "segments",
            "total_duration_seconds", "personas", "research_count",
            "poll_id", "assets_created", "dialogue_generated",
            "production_log", "production_time_seconds",
        }
        assert expected_keys.issubset(result.keys())

    def test_segment_types_include_all(self, runner: ShowRunnerAgent) -> None:
        runner.produce_show("Types", "general")
        ep = runner.current_episode
        assert ep is not None
        types = {s.type.value for s in ep.segments}
        assert "intro" in types
        assert "content" in types
        assert "guest" in types
        assert "ad" in types
        assert "outro" in types


# ── API integration (via TestClient) ──────────────────────────────────


class TestShowRunnerAPI:
    """Test the ShowRunner endpoints through the FastAPI TestClient.

    Uses the conftest client fixture with auth overrides.
    """

    @pytest.fixture(autouse=True)
    def _setup(self, client):
        """Use the TestClient fixture from conftest and reset the singleton."""
        self.client = client
        from broadcast.agents.router import _show_runner
        _show_runner.reset()

    def test_produce_endpoint(self) -> None:
        resp = self.client.post(
            "/api/agent/show-runner/produce",
            json={"topic": "The AI Revolution", "category": "technology"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["state"] == "ready"
        assert data["segments"] == 6

    def test_produce_no_topic_returns_422(self) -> None:
        resp = self.client.post(
            "/api/agent/show-runner/produce",
            json={"topic": ""},
        )
        assert resp.status_code == 422

    def test_produce_missing_topic_returns_422(self) -> None:
        resp = self.client.post(
            "/api/agent/show-runner/produce",
            json={},
        )
        assert resp.status_code == 422

    def test_run_endpoint(self) -> None:
        self.client.post(
            "/api/agent/show-runner/produce",
            json={"topic": "AI", "category": "technology"},
        )
        resp = self.client.post("/api/agent/show-runner/run", json={})
        assert resp.status_code == 200
        data = resp.json()
        assert data["state"] == "completed"
        assert len(data["segment_results"]) == 6

    def test_run_without_produce_returns_400(self) -> None:
        resp = self.client.post("/api/agent/show-runner/run", json={})
        assert resp.status_code == 400

    def test_status_endpoint(self) -> None:
        resp = self.client.get("/api/agent/show-runner/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["state"] == "idle"

    def test_status_after_produce(self) -> None:
        self.client.post(
            "/api/agent/show-runner/produce",
            json={"topic": "Status Check", "category": "science"},
        )
        resp = self.client.get("/api/agent/show-runner/status")
        data = resp.json()
        assert data["state"] == "ready"
        assert data["episode"] is not None

    def test_reset_endpoint(self) -> None:
        self.client.post(
            "/api/agent/show-runner/produce",
            json={"topic": "Reset Me", "category": "technology"},
        )
        resp = self.client.post("/api/agent/show-runner/reset")
        assert resp.status_code == 200
        assert resp.json()["state"] == "idle"

    def test_reset_clears_status(self) -> None:
        self.client.post(
            "/api/agent/show-runner/produce",
            json={"topic": "Clear Me"},
        )
        self.client.post("/api/agent/show-runner/reset")
        resp = self.client.get("/api/agent/show-runner/status")
        assert resp.json()["state"] == "idle"
        assert resp.json()["episode"] is None

"""Tests for M5 — Research Agent models, engine, backend, and agent."""

from __future__ import annotations

from time import time

import pytest
from pydantic import ValidationError

from broadcast.research.models import (
    FactCheck,
    ResearchResult,
    ResearchStatus,
    ResearchTopic,
    SourceCitation,
)
from broadcast.research.engine import (
    MockResearchBackend,
    ResearchAgent,
    ResearchEngine,
)


# ── Model tests ─────────────────────────────────────────────────────

class TestResearchTopicModel:
    def test_minimal_topic(self):
        topic = ResearchTopic(id="t1", query="test query")
        assert topic.id == "t1"
        assert topic.query == "test query"
        assert topic.status == ResearchStatus.QUEUED
        assert topic.segment_id == ""

    def test_topic_with_all_fields(self):
        topic = ResearchTopic(
            id="t1", query="test", segment_id="seg_1",
            segment_title="Test Segment", context="some context",
            status=ResearchStatus.IN_PROGRESS,
            created_at=100.0, completed_at=200.0,
        )
        assert topic.segment_title == "Test Segment"
        assert topic.status == ResearchStatus.IN_PROGRESS

    def test_topic_rejects_empty_id(self):
        with pytest.raises(ValidationError):
            ResearchTopic(id="", query="test")


class TestSourceCitationModel:
    def test_minimal_citation(self):
        cit = SourceCitation(url="https://example.com", title="Test", snippet="Snippet")
        assert cit.relevance_score == 0.0

    def test_citation_with_score(self):
        cit = SourceCitation(url="https://example.com", title="Test", snippet="Snippet", relevance_score=0.95)
        assert cit.relevance_score == 0.95


class TestFactCheckModel:
    def test_minimal_fact_check(self):
        fc = FactCheck(claim="Test claim", verdict="supported")
        assert fc.verdict == "supported"

    def test_fact_check_rejects_invalid_verdict(self):
        with pytest.raises(ValidationError):
            FactCheck(claim="Test", verdict="invalid")


class TestResearchResultModel:
    def test_minimal_result(self):
        result = ResearchResult(
            id="r1", topic_id="t1",
            summary="Summary", key_points=["A"],
            sources=[], fact_checks=[],
        )
        assert result.id == "r1"

    def test_result_with_sources(self):
        source = SourceCitation(url="https://ex.com", title="Ex", snippet="Snip")
        result = ResearchResult(
            id="r1", topic_id="t1",
            summary="Summary", key_points=["A"],
            sources=[source], fact_checks=[],
        )
        assert len(result.sources) == 1
        assert result.sources[0].url == "https://ex.com"


# ── MockResearchBackend tests ───────────────────────────────────────

class TestMockResearchBackend:
    def test_supports_known_topic(self):
        backend = MockResearchBackend()
        assert backend.supports_topic("technology")

    def test_supports_unknown_topic(self):
        backend = MockResearchBackend()
        assert not backend.supports_topic("quantum_xyz_nonexistent")

    def test_returns_template_for_known_topic(self):
        backend = MockResearchBackend()
        topic = ResearchTopic(id="t1", query="technology news today")
        result = backend.research(topic)
        assert len(result.key_points) >= 2
        assert len(result.sources) >= 1

    def test_returns_default_for_unknown_topic(self):
        backend = MockResearchBackend()
        topic = ResearchTopic(id="t1", query="something completely unknown and random")
        result = backend.research(topic)
        assert result.summary  # Should return the "general" template

    def test_technology_topic_has_fact_check(self):
        backend = MockResearchBackend()
        topic = ResearchTopic(id="t1", query="technology")
        result = backend.research(topic)
        assert len(result.fact_checks) >= 1


# ── ResearchEngine tests ────────────────────────────────────────────

class TestResearchEngine:
    def test_submit_returns_result_id(self):
        engine = ResearchEngine()
        backend = MockResearchBackend()
        topic = ResearchTopic(id="t1", query="weather", created_at=time())
        result_id = engine.submit(topic, backend)
        assert result_id.startswith("result_")

    def test_get_returns_result(self):
        engine = ResearchEngine()
        backend = MockResearchBackend()
        topic = ResearchTopic(id="t1", query="weather", created_at=time())
        result_id = engine.submit(topic, backend)
        result = engine.get(result_id)
        assert result is not None
        assert result.topic_id == "t1"

    def test_get_returns_none_for_missing(self):
        engine = ResearchEngine()
        assert engine.get("nonexistent") is None

    def test_list_returns_empty_initially(self):
        engine = ResearchEngine()
        assert engine.list() == []

    def test_list_returns_results_newest_first(self):
        engine = ResearchEngine()
        backend = MockResearchBackend()
        t1 = ResearchTopic(id="t1", query="technology", created_at=100.0)
        t2 = ResearchTopic(id="t2", query="sports", created_at=200.0)
        id1 = engine.submit(t1, backend)
        id2 = engine.submit(t2, backend)
        results = engine.list()
        assert results[0].topic_id == "t2"
        assert results[1].topic_id == "t1"

    def test_list_respects_limit(self):
        engine = ResearchEngine()
        backend = MockResearchBackend()
        for i in range(5):
            t = ResearchTopic(id=f"t{i}", query="technology", created_at=float(i))
            engine.submit(t, backend)
        assert len(engine.list(limit=2)) == 2

    def test_extract_topics_finds_matches(self):
        engine = ResearchEngine()
        topics = engine.extract_topics("technology and sports news today")
        assert "technology" in topics
        assert "sports" in topics

    def test_extract_topics_returns_empty_for_no_match(self):
        engine = ResearchEngine()
        topics = engine.extract_topics("something completely unrelated")
        assert topics == []


# ── ResearchAgent tests ─────────────────────────────────────────────

class TestResearchAgent:
    def test_agent_identity(self):
        agent = ResearchAgent()
        assert agent.agent_name == "Research"
        assert agent.agent_type == "research"

    def test_agent_start_stop(self):
        agent = ResearchAgent()
        assert not agent.running
        agent.start()
        assert agent.running
        agent.start()  # idempotent
        assert agent.running
        agent.stop()
        assert not agent.running
        agent.stop()  # idempotent
        assert not agent.running

    def test_submit_research_returns_result(self):
        agent = ResearchAgent()
        agent.start()
        result = agent.submit_research("technology trends")
        assert "summary" in result
        assert "key_points" in result

    def test_list_results(self):
        agent = ResearchAgent()
        agent.submit_research("technology")
        agent.submit_research("sports")
        results = agent.list_results()
        assert len(results) == 2

    def test_extract_topics_from_agent(self):
        agent = ResearchAgent()
        topics = agent.extract_topics("talk about technology and weather today")
        assert "technology" in topics
        assert "weather" in topics

    def test_get_context_for_segment_no_match(self):
        agent = ResearchAgent()
        context = agent.get_context_for_segment("nonexistent")
        assert context is None

    def test_get_context_for_segment_match(self):
        agent = ResearchAgent()
        agent.submit_research("technology", segment_id="seg_1")
        context = agent.get_context_for_segment("seg_1")
        assert context is not None
        assert "Research summary" in context
        assert "Key points" in context


# ── API endpoint tests ──────────────────────────────────────────────

_HEADERS = {"X-API-Key": "test-key"}


class TestResearchAPI:
    def test_submit_research(self, client):
        resp = client.post("/research/submit", json={"query": "technology trends"}, headers=_HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert "summary" in data
        assert "key_points" in data

    def test_submit_with_segment_context(self, client):
        resp = client.post("/research/submit", json={
            "query": "technology",
            "segment_id": "seg_test",
            "segment_title": "Test Segment",
            "context": "For broadcast use",
        }, headers=_HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert "summary" in data
        assert "key_points" in data

    def test_submit_empty_query(self, client):
        resp = client.post("/research/submit", json={"query": ""}, headers=_HEADERS)
        assert resp.status_code == 422

    def test_submit_missing_query(self, client):
        resp = client.post("/research/submit", json={}, headers=_HEADERS)
        assert resp.status_code == 422

    def test_list_results(self, client):
        # Submit first
        client.post("/research/submit", json={"query": "weather"}, headers=_HEADERS)
        resp = client.get("/research/results", headers=_HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1

    def test_get_result(self, client):
        submit_resp = client.post("/research/submit", json={"query": "sports"}, headers=_HEADERS)
        result = submit_resp.json()
        result_id = result["id"]
        resp = client.get(f"/research/results/{result_id}", headers=_HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == result_id

    def test_get_result_not_found(self, client):
        resp = client.get("/research/results/nonexistent", headers=_HEADERS)
        assert resp.status_code == 404

    def test_extract_topics(self, client):
        resp = client.post("/research/extract", json={"text": "technology and sports news"}, headers=_HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert "technology" in data["topics"]
        assert "sports" in data["topics"]

    def test_extract_topics_empty(self, client):
        resp = client.post("/research/extract", json={"text": ""}, headers=_HEADERS)
        assert resp.status_code == 422

    def test_extract_topics_no_match(self, client):
        resp = client.post("/research/extract", json={"text": "something completely unrelated"}, headers=_HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert data["topics"] == []

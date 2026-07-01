"""Tests for agent API endpoints."""

import pytest
from fastapi.testclient import TestClient
from broadcast.main import app
from broadcast.agents.router import _producer


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def clear_agent_state():
    """Ensure clean agent state between tests (module-level singletons)."""
    _producer._episodes.clear()
    yield


class TestEpisodeEndpoints:
    def test_create_episode(self, client):
        resp = client.post("/api/agent/episode", json={"title": "Morning Show"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Morning Show"
        assert "id" in data
        assert data["status"] == "draft"

    def test_create_episode_missing_title(self, client):
        resp = client.post("/api/agent/episode", json={"title": ""})
        assert resp.status_code == 422

    def test_list_episodes(self, client):
        client.post("/api/agent/episode", json={"title": "Show A"})
        client.post("/api/agent/episode", json={"title": "Show B"})
        resp = client.get("/api/agent/episodes")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2

    def test_get_episode(self, client):
        create = client.post("/api/agent/episode", json={"title": "My Show"})
        ep_id = create.json()["id"]
        resp = client.get(f"/api/agent/episode/{ep_id}")
        assert resp.status_code == 200
        assert resp.json()["title"] == "My Show"

    def test_get_nonexistent_episode(self, client):
        resp = client.get("/api/agent/episode/nonexistent")
        assert resp.status_code == 404

    def test_add_segment(self, client):
        create = client.post("/api/agent/episode", json={"title": "Show"})
        ep_id = create.json()["id"]
        resp = client.post(
            f"/api/agent/episode/{ep_id}/segment",
            json={"id": "intro", "type": "intro", "title": "Welcome", "duration_seconds": 30},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["segments"]) == 1
        assert data["segments"][0]["id"] == "intro"


class TestDirectorEndpoints:
    def test_director_status_initial(self, client):
        resp = client.get("/api/agent/director/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["current_segment"] is None
        assert data["has_more"] is False
        assert data["running"] is False

    def test_load_episode(self, client):
        create = client.post("/api/agent/episode", json={"title": "Show"})
        ep_id = create.json()["id"]
        # Add segments
        client.post(f"/api/agent/episode/{ep_id}/segment",
                    json={"id": "intro", "type": "intro", "title": "Intro"})
        client.post(f"/api/agent/episode/{ep_id}/segment",
                    json={"id": "main", "type": "content", "title": "Main Topic"})
        # Load into director
        resp = client.post(f"/api/agent/episode/{ep_id}/load")
        assert resp.status_code == 200
        data = resp.json()
        assert data["loaded"] is True
        assert data["title"] == "Show"
        assert data["segment_count"] == 2

    def test_director_next_segment(self, client):
        create = client.post("/api/agent/episode", json={"title": "Show"})
        ep_id = create.json()["id"]
        client.post(f"/api/agent/episode/{ep_id}/segment",
                    json={"id": "intro", "type": "intro", "title": "Intro"})
        client.post(f"/api/agent/episode/{ep_id}/load")
        resp = client.post("/api/agent/director/next")
        assert resp.status_code == 200
        data = resp.json()
        assert data["segment"]["id"] == "intro"
        assert data["has_more"] is False  # only one segment added

    def test_director_generate_dialogue(self, client):
        create = client.post("/api/agent/episode", json={"title": "Show"})
        ep_id = create.json()["id"]
        client.post(f"/api/agent/episode/{ep_id}/segment",
                    json={"id": "intro", "type": "intro", "title": "Welcome!"})
        client.post(f"/api/agent/episode/{ep_id}/load")
        client.post("/api/agent/director/next")  # advance to first segment
        resp = client.post("/api/agent/director/generate")
        assert resp.status_code == 200
        data = resp.json()
        assert "host" in data
        assert "cohost" in data
        assert data["segment_id"] == "intro"
        assert len(data["host"]["lines"]) >= 1
        assert data["host"]["lines"][0]["speaker"] == "Host"


class TestDialogueEndpoints:
    def test_host_dialogue(self, client):
        resp = client.post(
            "/api/agent/host/dialogue",
            json={"id": "test", "type": "intro", "title": "Hello World"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["lines"]) >= 1

    def test_cohost_dialogue(self, client):
        resp = client.post(
            "/api/agent/cohost/dialogue",
            json={"id": "test", "type": "content", "title": "Tech News"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["lines"]) >= 1

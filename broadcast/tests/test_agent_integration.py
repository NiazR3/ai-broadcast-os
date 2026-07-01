"""Integration tests for the complete agent-driven broadcast lifecycle."""

import pytest
from fastapi.testclient import TestClient
from broadcast.main import app
from broadcast.agents.router import _producer


@pytest.fixture(autouse=True)
def clear_agent_state():
    """Ensure clean agent state between tests (module-level singletons)."""
    _producer._episodes.clear()
    yield


class TestAgentBroadcastLifecycle:
    """Full lifecycle: create episode -> add segments -> load -> advance -> generate dialogue."""

    def test_full_agent_lifecycle(self):
        client = TestClient(app)

        # 1. Create episode
        resp = client.post("/api/agent/episode", json={"title": "Morning Show"})
        assert resp.status_code == 200
        ep = resp.json()
        ep_id = ep["id"]
        assert ep["title"] == "Morning Show"

        # 2. Add segments
        segments = [
            {"id": "intro", "type": "intro", "title": "Welcome!", "duration_seconds": 30},
            {"id": "topic1", "type": "content", "title": "AI News", "duration_seconds": 120},
            {"id": "outro", "type": "outro", "title": "See You Next Time", "duration_seconds": 15},
        ]
        for seg in segments:
            resp = client.post(f"/api/agent/episode/{ep_id}/segment", json=seg)
            assert resp.status_code == 200

        # 3. Verify episode has 3 segments
        resp = client.get(f"/api/agent/episode/{ep_id}")
        assert resp.status_code == 200
        assert len(resp.json()["segments"]) == 3

        # 4. Load into director
        resp = client.post(f"/api/agent/episode/{ep_id}/load")
        assert resp.status_code == 200
        assert resp.json()["loaded"] is True

        # 5. Check director status (before first segment)
        resp = client.get("/api/agent/director/status")
        assert resp.json()["current_segment"] is None

        # 6. Advance to intro
        resp = client.post("/api/agent/director/next")
        assert resp.status_code == 200
        assert resp.json()["segment"]["id"] == "intro"
        assert resp.json()["has_more"] is True

        # 7. Generate dialogue for intro
        resp = client.post("/api/agent/director/generate")
        assert resp.status_code == 200
        data = resp.json()
        assert data["segment_id"] == "intro"
        assert len(data["host"]["lines"]) >= 1
        assert data["host"]["lines"][0]["speaker"] == "Host"
        assert len(data["cohost"]["lines"]) >= 1

        # 8. Advance through remaining segments
        client.post("/api/agent/director/next")  # topic1
        resp = client.post("/api/agent/director/next")  # outro
        assert resp.json()["segment"]["id"] == "outro"

        # 9. Try next past end
        resp = client.post("/api/agent/director/next")
        assert resp.status_code == 400  # No more segments

    def test_list_episodes_returns_all(self):
        client = TestClient(app)
        client.post("/api/agent/episode", json={"title": "Ep 1"})
        client.post("/api/agent/episode", json={"title": "Ep 2"})
        resp = client.get("/api/agent/episodes")
        data = resp.json()
        assert len(data) == 2
        titles = [e["title"] for e in data]
        assert "Ep 1" in titles
        assert "Ep 2" in titles

    def test_standalone_dialogue(self):
        client = TestClient(app)

        # Host dialogue
        resp = client.post("/api/agent/host/dialogue", json={
            "id": "test", "type": "content", "title": "Space Exploration",
        })
        assert resp.status_code == 200
        host = resp.json()
        assert len(host["lines"]) >= 1
        assert host["lines"][0]["speaker"] == "Host"

        # Co-host dialogue
        resp = client.post("/api/agent/cohost/dialogue", json={
            "id": "test", "type": "content", "title": "Space Exploration",
        })
        assert resp.status_code == 200
        cohost = resp.json()
        assert len(cohost["lines"]) >= 1
        assert cohost["lines"][0]["speaker"] == "Co-Host"

        # Should talk about the topic
        host_text = " ".join(l["text"] for l in host["lines"])
        assert "Space" in host_text

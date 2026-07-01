"""Tests for Broadcast API endpoints.

RED phase: these fail until routes are wired into main.py.
GREEN phase: module-level Multiplexer is configured inline, subprocess.Popen
is mocked so start_broadcast succeeds without FFmpeg.
"""

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from broadcast.api.routes import get_mux
from broadcast.main import app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _configure_platform(platform_name: str, stream_key: str) -> None:
    """Give a platform on the module-level multiplexer a valid RTMP URL."""
    mux = get_mux()
    mux.update_platform(platform_name, stream_key)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_get_broadcast_status():
    """GET /api/broadcast/status returns active flag and platform dict."""
    client = TestClient(app)
    resp = client.get("/api/broadcast/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "active" in data
    assert "platforms" in data


def test_get_scenes_when_obs_not_connected():
    """GET /api/broadcast/scenes returns 503 when OBS is disconnected."""
    client = TestClient(app)
    resp = client.get("/api/broadcast/scenes")
    assert resp.status_code == 503
    data = resp.json()
    assert "detail" in data


@patch("broadcast.streaming.multiplexer.subprocess.Popen")
def test_broadcast_start_stop_cycle(mock_popen):
    """Start, verify active, stop, verify inactive."""
    mock_process = MagicMock()
    mock_process.pid = 12345
    mock_popen.return_value = mock_process

    # Give the module-level mux at least one configured platform
    _configure_platform("twitch", "live_12345")

    client = TestClient(app)

    # Start broadcast
    start_resp = client.post("/api/broadcast/start")
    assert start_resp.status_code == 200
    assert start_resp.json()["active"] is True

    # Status shows active
    status_resp = client.get("/api/broadcast/status")
    assert status_resp.json()["active"] is True

    # Stop broadcast
    stop_resp = client.post("/api/broadcast/stop")
    assert stop_resp.status_code == 200
    assert stop_resp.json()["active"] is False

    # Status reflects inactive
    final_resp = client.get("/api/broadcast/status")
    assert final_resp.json()["active"] is False


def test_get_platforms():
    """GET /api/broadcast/platforms returns all configured platforms."""
    client = TestClient(app)
    resp = client.get("/api/broadcast/platforms")
    assert resp.status_code == 200
    platforms = resp.json()
    assert "twitch" in platforms
    assert "youtube" in platforms
    assert "facebook" in platforms


def test_update_platforms_validates():
    """POST /api/broadcast/platforms updates and validates stream keys."""
    client = TestClient(app)
    resp = client.post(
        "/api/broadcast/platforms",
        json={
            "twitch": "new_key_123",
            "youtube": "",
            "facebook": "fb_key_456",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["twitch"]["rtmp_url"].endswith("new_key_123")
    assert data["youtube"]["error"] is not None


@patch("broadcast.streaming.multiplexer.subprocess.Popen")
def test_websocket_endpoint(mock_popen):
    """WebSocket receives live broadcast events via the event bus."""
    mock_process = MagicMock()
    mock_process.pid = 12345
    mock_popen.return_value = mock_process

    _configure_platform("twitch", "live_12345")

    client = TestClient(app)
    with client.websocket_connect("/api/broadcast/ws") as ws:
        client.post("/api/broadcast/start")
        data = ws.receive_json()
        assert data["type"] == "broadcast.started"

    # Clean up: stop broadcast so next test gets a clean state
    client.post("/api/broadcast/stop")


def test_duplicate_persona_endpoint(client):
    """Test duplicating a persona via the API endpoint."""

    # First create a persona to duplicate
    create_resp = client.post(
        "/api/agent/personas",
        json={
            "name": "Original Person",
            "agent_type": "host",
            "personality_traits": ["enthusiastic", "knowledgeable"],
            "catchphrases": ["Let's go!"],
            "voice_style": "energetic",
            "default_emotion": "excited",
            "emotional_range": ["excited", "curious", "enthusiastic"],
            "background_story": "A test persona",
        },
    )
    assert create_resp.status_code == 200
    original_persona = create_resp.json()
    original_id = original_persona["id"]

    # Duplicate the persona
    duplicate_resp = client.post(f"/api/agent/personas/{original_id}/duplicate")
    assert duplicate_resp.status_code == 200
    duplicated_persona = duplicate_resp.json()

    # Verify the duplicated persona
    assert duplicated_persona["id"] != original_id
    assert duplicated_persona["name"] == "Original Person (Copy)"
    assert duplicated_persona["agent_type"] == original_persona["agent_type"]
    assert duplicated_persona["personality_traits"] == original_persona["personality_traits"]
    assert duplicated_persona["catchphrases"] == original_persona["catchphrases"]
    assert duplicated_persona["voice_style"] == original_persona["voice_style"]
    assert duplicated_persona["default_emotion"] == original_persona["default_emotion"]
    assert duplicated_persona["emotional_range"] == original_persona["emotional_range"]
    assert duplicated_persona["background_story"] == original_persona["background_story"]

    # Verify both personas exist
    list_resp = client.get("/api/agent/personas")
    assert list_resp.status_code == 200
    personas = list_resp.json()
    assert len(personas) == 2

    # Verify we can get both by ID
    get_original = client.get(f"/api/agent/personas/{original_id}")
    assert get_original.status_code == 200
    get_duplicate = client.get(f"/api/agent/personas/{duplicated_persona['id']}")
    assert get_duplicate.status_code == 200

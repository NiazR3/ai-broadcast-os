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
    """GET /broadcast/status returns active flag and platform dict."""
    client = TestClient(app)
    resp = client.get("/broadcast/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "active" in data
    assert "platforms" in data


def test_get_scenes_when_obs_not_connected():
    """GET /broadcast/scenes returns 503 when OBS is disconnected."""
    client = TestClient(app)
    resp = client.get("/broadcast/scenes")
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
    start_resp = client.post("/broadcast/start")
    assert start_resp.status_code == 200
    assert start_resp.json()["active"] is True

    # Status shows active
    status_resp = client.get("/broadcast/status")
    assert status_resp.json()["active"] is True

    # Stop broadcast
    stop_resp = client.post("/broadcast/stop")
    assert stop_resp.status_code == 200
    assert stop_resp.json()["active"] is False

    # Status reflects inactive
    final_resp = client.get("/broadcast/status")
    assert final_resp.json()["active"] is False


def test_get_platforms():
    """GET /broadcast/platforms returns all configured platforms."""
    client = TestClient(app)
    resp = client.get("/broadcast/platforms")
    assert resp.status_code == 200
    platforms = resp.json()
    assert "twitch" in platforms
    assert "youtube" in platforms
    assert "facebook" in platforms


def test_update_platforms_validates():
    """POST /broadcast/platforms updates and validates stream keys."""
    client = TestClient(app)
    resp = client.post(
        "/broadcast/platforms",
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

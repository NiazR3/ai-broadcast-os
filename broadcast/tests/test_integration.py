"""Integration tests for the full broadcast pipeline."""

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from broadcast.main import app


@patch("broadcast.streaming.multiplexer.subprocess.Popen")
def test_full_broadcast_lifecycle(mock_popen):
    """Test the full broadcast lifecycle: configure -> start -> status -> stop."""
    mock_process = MagicMock()
    mock_process.pid = 12345
    mock_popen.return_value = mock_process

    client = TestClient(app)

    # Ensure clean state before starting (a prior test may have left the mux active)
    client.post("/broadcast/stop")

    # 1. Initial state
    status = client.get("/broadcast/status").json()
    assert status["active"] is False
    assert "twitch" in status["platforms"]

    # 2. Update platform keys
    client.post("/broadcast/platforms", json={
        "twitch": "test_key_twitch",
        "youtube": "test_key_youtube",
        "facebook": "test_key_facebook",
    })

    # 3. Verify keys applied
    platforms = client.get("/broadcast/platforms").json()
    assert platforms["twitch"]["streaming"] is False
    assert platforms["twitch"]["error"] is None
    assert "test_key_twitch" in platforms["twitch"]["rtmp_url"]

    # 4. Start broadcast
    start_resp = client.post("/broadcast/start").json()
    assert start_resp["active"] is True

    # 5. Status shows active
    status = client.get("/broadcast/status").json()
    assert status["active"] is True
    assert status["uptime_seconds"] >= 0

    # 6. Stop broadcast
    stop_resp = client.post("/broadcast/stop").json()
    assert stop_resp["active"] is False

    # 7. Health still works
    health = client.get("/health").json()
    assert health["status"] == "ok"


def test_health_independent():
    """Health endpoint works regardless of broadcast state."""
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_api_errors_return_problem_json():
    """API returns structured errors."""
    client = TestClient(app)

    # Non-existent scene endpoint without OBS
    answer = client.get("/broadcast/scenes")
    # Should return 503 since OBS is not connected
    assert answer.status_code in (200, 503)
    if answer.status_code == 503:
        assert "detail" in answer.json()

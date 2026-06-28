"""Test configuration and fixtures for the broadcast test suite."""

import pytest
from broadcast.api.routes import get_mux


@pytest.fixture(autouse=True)
def reset_multiplexer():
    """Reset the module-level Multiplexer singleton before each test.

    Ensures tests don't leak state (active broadcasts, configured platforms).
    """
    mux = get_mux()
    mux.stop_broadcast()
    for name in list(mux.status.platforms.keys()):
        mux.update_platform(name, "")
    yield


@pytest.fixture
def client():
    """Provide a TestClient with API key verification overridden for testing."""
    from fastapi.testclient import TestClient
    from broadcast.main import app
    from broadcast.auth import verify_api_key
    from fastapi import Header, HTTPException

    async def _test_verify_api_key(x_api_key: str | None = Header(None)):
        if not x_api_key or x_api_key != "test-key":
            raise HTTPException(status_code=403, detail="Invalid API key")

    app.dependency_overrides[verify_api_key] = _test_verify_api_key
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(verify_api_key, None)

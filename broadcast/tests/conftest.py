"""Test configuration and fixtures for the broadcast test suite."""

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from broadcast.api.routes import get_mux
from broadcast.agents.router import _persona_repo
from broadcast.auth import verify_api_key
from broadcast.config import Settings
from broadcast.main import app
from broadcast.auth import verify_api_key
from fastapi import Header


@pytest.fixture(autouse=True)
def reset_multiplexer():
    """Reset the module-level Multiplexer singleton before each test."""
    mux = get_mux()
    mux.stop_broadcast()
    for name in list(mux.status.platforms.keys()):
        mux.update_platform(name, "")
    yield


@pytest.fixture(autouse=True)
def clear_personas():
    """Clear the persona repository before each test to ensure test isolation."""
    for persona in list(_persona_repo.list()):
        _persona_repo.delete(persona.id)
    yield


@pytest.fixture
def client():
    """Provide a TestClient with API key verification overridden for testing."""
    async def _test_verify_api_key(x_api_key: str | None = Header(None)):
        """Dependency used to validate mobile connections."""
        settings = Settings()
        if not settings.api_key:
            return  # No key configured = no auth required (development mode)
        if not x_api_key:
            raise HTTPException(status_code=401, detail="Missing X-API-Key header")
        if x_api_key != settings.api_key:
            raise HTTPException(status_code=403, detail="Invalid API key")

    app.dependency_overrides[verify_api_key] = _test_verify_api_key
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(verify_api_key, None)
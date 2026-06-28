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

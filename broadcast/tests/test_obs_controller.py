"""Tests for OBS WebSocket controller."""

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from broadcast.obs.controller import ObsController, ObsConnectionError


@pytest.mark.asyncio
async def test_connect_success():
    """Connect patches obsws to verify controller wiring."""
    controller = ObsController(host="localhost", port=4455, password="")
    with patch("broadcast.obs.controller.obsws") as mock_obsws:
        mock_instance = MagicMock()
        mock_obsws.return_value = mock_instance
        result = await controller.connect()
        assert result is True
        assert controller.connected is True


@pytest.mark.asyncio
async def test_connect_failure_raises():
    """Connection refused is wrapped in ObsConnectionError."""
    controller = ObsController(host="localhost", port=4455, password="")
    with patch("broadcast.obs.controller.obsws") as mock_obsws:
        mock_instance = MagicMock()
        mock_obsws.return_value = mock_instance
        mock_instance.connect.side_effect = ConnectionRefusedError("OBS not running")
        with pytest.raises(ObsConnectionError, match="OBS not running"):
            await controller.connect()
    assert controller.connected is False


@pytest.mark.asyncio
async def test_connect_generic_exception():
    """Non-ConnectionRefused error is wrapped generically."""
    controller = ObsController(host="localhost", port=4455, password="")
    with patch("broadcast.obs.controller.obsws") as mock_obsws:
        mock_instance = MagicMock()
        mock_obsws.return_value = mock_instance
        mock_instance.connect.side_effect = Exception("timeout")
        with pytest.raises(ObsConnectionError, match="Failed to connect: timeout"):
            await controller.connect()


@pytest.mark.asyncio
async def test_switch_scene():
    """Switch scene calls obsws.call with SetCurrentProgramScene."""
    controller = ObsController(host="localhost", port=4455, password="")
    with patch("broadcast.obs.controller.obsws") as mock_obsws:
        mock_instance = MagicMock()
        mock_obsws.return_value = mock_instance
        controller.ws = mock_instance
        controller._connected = True
        result = await controller.switch_scene("Main")
        assert result is True
        mock_instance.call.assert_called_once()


@pytest.mark.asyncio
async def test_get_current_scene():
    """get_current_scene returns the scene name from the response."""
    controller = ObsController(host="localhost", port=4455, password="")
    with patch("broadcast.obs.controller.obsws") as mock_obsws:
        mock_instance = MagicMock()
        mock_obsws.return_value = mock_instance
        controller.ws = mock_instance
        controller._connected = True
        mock_response = MagicMock()
        mock_response.getSceneName.return_value = "Live"
        mock_instance.call.return_value = mock_response
        scene = await controller.get_current_scene()
        assert scene == "Live"


@pytest.mark.asyncio
async def test_get_scene_list():
    """get_scene_list returns a list of scene name strings."""
    controller = ObsController(host="localhost", port=4455, password="")
    with patch("broadcast.obs.controller.obsws") as mock_obsws:
        mock_instance = MagicMock()
        mock_obsws.return_value = mock_instance
        controller.ws = mock_instance
        controller._connected = True
        mock_response = MagicMock()
        mock_response.getScenes.return_value = [
            {"sceneName": "Intro"},
            {"sceneName": "Main"},
            {"sceneName": "Outro"},
        ]
        mock_instance.call.return_value = mock_response
        scenes = await controller.get_scene_list()
        assert scenes == ["Intro", "Main", "Outro"]


@pytest.mark.asyncio
async def test_set_source_visibility():
    """set_source_visibility returns True on success."""
    controller = ObsController(host="localhost", port=4455, password="")
    with patch("broadcast.obs.controller.obsws") as mock_obsws:
        mock_instance = MagicMock()
        mock_obsws.return_value = mock_instance
        controller.ws = mock_instance
        controller._connected = True
        result = await controller.set_source_visibility("Webcam", True)
        assert result is True
        assert mock_instance.call.call_count == 3


def test_disconnect_when_not_connected():
    """disconnect with None ws does not raise."""
    controller = ObsController(host="localhost", port=4455, password="")
    controller.ws = None
    asyncio.run(controller.disconnect())


@pytest.mark.asyncio
async def test_methods_raise_when_disconnected():
    """All scene/source methods raise ObsConnectionError when not connected."""
    controller = ObsController(host="localhost", port=4455, password="")
    controller.ws = None
    controller._connected = False

    with pytest.raises(ObsConnectionError, match="Not connected"):
        await controller.switch_scene("Main")
    with pytest.raises(ObsConnectionError, match="Not connected"):
        await controller.get_current_scene()
    with pytest.raises(ObsConnectionError, match="Not connected"):
        await controller.get_scene_list()
    with pytest.raises(ObsConnectionError, match="Not connected"):
        await controller.set_source_visibility("Cam", True)

"""OBS WebSocket controller using obs-websocket-py."""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from obswebsocket import obsws, requests as obs_requests

logger = logging.getLogger(__name__)


class ObsConnectionError(Exception):
    """Raised when OBS WebSocket connection fails."""


class ObsController:
    """Manages OBS scenes and sources via WebSocket.

    Wraps the synchronous obs-websocket-py library in an async interface
    using asyncio.to_thread for all blocking calls.
    """

    def __init__(self, host: str = "localhost", port: int = 4455, password: str = "") -> None:
        self.host = host
        self.port = port
        self.password = password
        self.ws: Optional[obsws] = None
        self._connected = False

    @property
    def connected(self) -> bool:
        return self._connected

    async def connect(self) -> bool:
        """Connect to OBS WebSocket server.

        Returns True on success. Raises ObsConnectionError on failure.
        """
        try:
            self.ws = obsws(self.host, self.port, self.password)
            await asyncio.to_thread(self.ws.connect)
            self._connected = True
            logger.info("Connected to OBS at %s:%s", self.host, self.port)
            return True
        except ConnectionRefusedError as exc:
            raise ObsConnectionError("OBS not running") from exc
        except Exception as exc:
            raise ObsConnectionError(f"Failed to connect: {exc}") from exc

    async def disconnect(self) -> None:
        """Disconnect from OBS WebSocket. Safe to call when not connected."""
        if self.ws and self._connected:
            await asyncio.to_thread(self.ws.disconnect)
            self._connected = False
            logger.info("Disconnected from OBS")

    async def switch_scene(self, scene_name: str) -> bool:
        """Switch to a named scene in OBS. Returns True on success."""
        if not self.ws or not self._connected:
            raise ObsConnectionError("Not connected to OBS")
        try:
            await asyncio.to_thread(self.ws.call, obs_requests.SetCurrentProgramScene(sceneName=scene_name))
            logger.info("Switched to scene: %s", scene_name)
            return True
        except Exception as exc:
            raise ObsConnectionError(f"Failed to switch scene: {exc}") from exc

    async def get_current_scene(self) -> str:
        """Return the name of the currently active scene."""
        if not self.ws or not self._connected:
            raise ObsConnectionError("Not connected to OBS")
        try:
            resp = await asyncio.to_thread(self.ws.call, obs_requests.GetCurrentProgramScene())
            return resp.getSceneName()
        except Exception as exc:
            raise ObsConnectionError(f"Failed to get current scene: {exc}") from exc

    async def get_scene_list(self) -> list[str]:
        """Return the list of all scene names."""
        if not self.ws or not self._connected:
            raise ObsConnectionError("Not connected to OBS")
        try:
            resp = await asyncio.to_thread(self.ws.call, obs_requests.GetSceneList())
            return [s["sceneName"] for s in resp.getScenes()]
        except Exception as exc:
            raise ObsConnectionError(f"Failed to get scene list: {exc}") from exc

    async def set_source_visibility(self, source_name: str, visible: bool) -> bool:
        """Show or hide a source in the current scene. Returns True on success."""
        if not self.ws or not self._connected:
            raise ObsConnectionError("Not connected to OBS")
        try:
            await asyncio.to_thread(
                self.ws.call,
                obs_requests.SetSourceVisibility(sourceName=source_name, visible=visible),
            )
            return True
        except Exception as exc:
            raise ObsConnectionError(f"Failed to set source visibility: {exc}") from exc

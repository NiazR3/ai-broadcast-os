"""OBS WebSocket controller using obs-websocket-py."""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from obswebsocket import obsws, requests as obs_requests

logger = logging.getLogger(__name__)

OBS_REQUEST_TIMEOUT = 15  # seconds — prevents thread pool deadlock on hung OBS


class ObsConnectionError(Exception):
    """Raised when OBS WebSocket connection fails."""


class ObsController:
    """Manages OBS scenes and sources via WebSocket.

    Wraps the synchronous obs-websocket-py library in an async interface
    using asyncio.to_thread for all blocking calls.
    """

    def __init__(self, host: str = "localhost", port: int = 4455, password: str = "") -> None:  # nosec - password default empty = no auth in dev
        self.host = host
        self.port = port
        self.password = password
        self.ws: Optional[obsws] = None
        self._connected = False

    def _on_ws_disconnect(self, _ws: obsws) -> None:
        """Callback invoked by obsws when the WebSocket disconnects in background."""
        self._connected = False
        logger.warning("OBS WebSocket disconnected (background)")

    @property
    def connected(self) -> bool:
        return self._connected

    async def _call(self, request) -> object:
        """Call an OBS request with a timeout. Prevents thread-pool deadlock."""
        return await asyncio.wait_for(
            asyncio.to_thread(self.ws.call, request),
            timeout=OBS_REQUEST_TIMEOUT,
        )

    async def connect(self) -> bool:
        """Connect to OBS WebSocket server.

        Returns True on success. Raises ObsConnectionError on failure.
        Idempotent: if already connected, returns True immediately.
        """
        if self._connected:
            logger.debug("Already connected to OBS at %s:%s", self.host, self.port)
            return True
        ws: Optional[obsws] = None
        try:
            ws = obsws(self.host, self.port, self.password, on_disconnect=self._on_ws_disconnect)
            await asyncio.wait_for(
                asyncio.to_thread(ws.connect),
                timeout=OBS_REQUEST_TIMEOUT,
            )
            self.ws = ws
            self._connected = True
            logger.info("Connected to OBS at %s:%s", self.host, self.port)
            return True
        except ConnectionRefusedError as exc:
            raise ObsConnectionError("OBS not running") from exc
        except (asyncio.TimeoutError, Exception) as exc:
            # Clean up partially-created obsws to avoid leaking background threads
            if ws is not None:
                try:
                    await asyncio.wait_for(
                        asyncio.to_thread(ws.disconnect),
                        timeout=5,
                    )
                except Exception:
                    pass  # best-effort cleanup
            raise ObsConnectionError(f"Failed to connect: {exc}") from exc

    async def disconnect(self) -> None:
        """Disconnect from OBS WebSocket. Safe to call when not connected."""
        if self.ws and self._connected:
            try:
                await asyncio.wait_for(
                    asyncio.to_thread(self.ws.disconnect),
                    timeout=OBS_REQUEST_TIMEOUT,
                )
            except Exception:
                logger.exception("Error during OBS disconnect")
            finally:
                self._connected = False
                logger.info("Disconnected from OBS")

    async def create_scene(self, scene_name: str) -> bool:
        """Create a new scene in OBS. Returns True on success."""
        if not self.ws or not self._connected:
            raise ObsConnectionError("Not connected to OBS")
        try:
            await self._call(obs_requests.CreateScene(sceneName=scene_name))
            logger.info("Created scene: %s", scene_name)
            return True
        except asyncio.TimeoutError:
            raise ObsConnectionError("Timeout creating scene: OBS may be unresponsive")
        except Exception as exc:
            raise ObsConnectionError(f"Failed to create scene: {exc}") from exc

    async def switch_scene(self, scene_name: str) -> bool:
        """Switch to a named scene in OBS. Returns True on success."""
        if not self.ws or not self._connected:
            raise ObsConnectionError("Not connected to OBS")
        try:
            await self._call(obs_requests.SetCurrentProgramScene(sceneName=scene_name))
            logger.info("Switched to scene: %s", scene_name)
            return True
        except asyncio.TimeoutError:
            raise ObsConnectionError("Timeout switching scene: OBS may be unresponsive")
        except Exception as exc:
            raise ObsConnectionError(f"Failed to switch scene: {exc}") from exc

    async def get_current_scene(self) -> str:
        """Return the name of the currently active scene."""
        if not self.ws or not self._connected:
            raise ObsConnectionError("Not connected to OBS")
        try:
            resp = await self._call(obs_requests.GetCurrentProgramScene())
            return resp.getSceneName()
        except asyncio.TimeoutError:
            raise ObsConnectionError("Timeout getting current scene")
        except Exception as exc:
            raise ObsConnectionError(f"Failed to get current scene: {exc}") from exc

    async def get_scene_list(self) -> list[str]:
        """Return the list of all scene names."""
        if not self.ws or not self._connected:
            raise ObsConnectionError("Not connected to OBS")
        try:
            resp = await self._call(obs_requests.GetSceneList())
            return [s["sceneName"] for s in resp.getScenes()]
        except asyncio.TimeoutError:
            raise ObsConnectionError("Timeout getting scene list")
        except Exception as exc:
            raise ObsConnectionError(f"Failed to get scene list: {exc}") from exc

    async def set_source_visibility(self, source_name: str, visible: bool) -> bool:
        """Show or hide a source in the current scene. Returns True on success."""
        if not self.ws or not self._connected:
            raise ObsConnectionError("Not connected to OBS")
        try:
            current_scene = await self.get_current_scene()
            resp = await self._call(
                obs_requests.GetSceneItemId(
                    sceneName=current_scene,
                    sourceName=source_name,
                    searchOffset=-1,
                ),
            )
            if not resp.status:
                raise ObsConnectionError(
                    f"Scene item not found for source '{source_name}' in scene '{current_scene}'"
                )
            scene_item_id = resp.getSceneItemId()

            # Re-check current scene to mitigate TOCTOU before the visibility write
            still_current = await self.get_current_scene()
            if still_current != current_scene:
                logger.warning(
                    "Scene switched from '%s' to '%s' during visibility operation; using new scene",
                    current_scene, still_current,
                )

            await self._call(
                obs_requests.SetSceneItemEnabled(
                    sceneName=still_current,
                    sceneItemId=scene_item_id,
                    sceneItemEnabled=visible,
                ),
            )
            logger.info(
                "Set source '%s' visibility to %s in scene '%s'",
                source_name, visible, still_current,
            )
            return True
        except ObsConnectionError:
            raise
        except asyncio.TimeoutError:
            raise ObsConnectionError("Timeout setting source visibility")
        except Exception as exc:
            raise ObsConnectionError(f"Failed to set source visibility: {exc}") from exc

    async def get_scene_sources(self, scene_name: str) -> list[dict]:
        """Return all sources in a scene."""
        if not self.ws or not self._connected:
            raise ObsConnectionError("Not connected to OBS")
        try:
            resp = await self._call(obs_requests.GetSceneItemList(sceneName=scene_name))
            try:
                items = resp.getSceneItems()
            except AttributeError:
                items = resp.datain.get("sceneItems", [])
            return [
                {
                    "id": item.get("sceneItemId"),
                    "name": item.get("sourceName", "unknown"),
                    "enabled": item.get("sceneItemEnabled", False),
                    "type": item.get("sourceType", "unknown"),
                }
                for item in items
            ]
        except asyncio.TimeoutError:
            raise ObsConnectionError("Timeout getting scene sources")
        except Exception as exc:
            raise ObsConnectionError(f"Failed to get scene sources: {exc}") from exc

    async def set_source_visibility_in_scene(
        self, scene_name: str, source_id: int, enabled: bool
    ) -> bool:
        """Show or hide a source by scene_item_id in a specific scene."""
        if not self.ws or not self._connected:
            raise ObsConnectionError("Not connected to OBS")
        try:
            await self._call(
                obs_requests.SetSceneItemEnabled(
                    sceneName=scene_name,
                    sceneItemId=source_id,
                    sceneItemEnabled=enabled,
                ),
            )
            logger.info(
                "Set source item %s visibility to %s in scene '%s'",
                source_id, enabled, scene_name,
            )
            return True
        except asyncio.TimeoutError:
            raise ObsConnectionError("Timeout setting source visibility")
        except Exception as exc:
            raise ObsConnectionError(f"Failed to set source visibility: {exc}") from exc

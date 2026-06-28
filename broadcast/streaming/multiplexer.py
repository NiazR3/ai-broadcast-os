"""RTMP Multiplex Engine — receives one stream, pushes to N platforms via FFmpeg."""

from __future__ import annotations
import logging
import subprocess
from time import time
from typing import Optional
from broadcast.streaming.platforms import (
    Platform, PlatformStatus, BroadcastStatus, build_rtmp_url,
)
from broadcast.config import Settings

logger = logging.getLogger(__name__)


class Multiplexer:
    """Manages a single broadcast session — starts/stops FFmpeg multiplex subprocess."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._process: Optional[subprocess.Popen] = None
        self._status = BroadcastStatus()
        self._init_platforms()

    def _init_platforms(self) -> None:
        """Build PlatformStatus entries from configured stream keys."""
        keys: dict[str, str] = self.settings.platform_stream_keys
        for platform_name in ("twitch", "youtube", "facebook"):
            try:
                plat = Platform(platform_name)
                key = keys.get(platform_name, "")
                if not key:
                    self._status.platforms[platform_name] = PlatformStatus(
                        platform=plat,
                        streaming=False,
                        error="Stream key not configured",
                    )
                    continue
                url = build_rtmp_url(plat, key)
                self._status.platforms[platform_name] = PlatformStatus(
                    platform=plat,
                    streaming=False,
                    rtmp_url=url,
                )
            except ValueError as exc:
                self._status.platforms[platform_name] = PlatformStatus(
                    platform=Platform(platform_name),
                    streaming=False,
                    error=str(exc),
                )

    @property
    def status(self) -> BroadcastStatus:
        # Detect stale FFmpeg death: process exited but we still think we're active
        if self._process is not None and self._status.active:
            ret = self._process.poll()
            if isinstance(ret, int):
                logger.warning(
                    "FFmpeg process (PID %d) exited unexpectedly with code %d",
                    self._process.pid, ret,
                )
                self._status.active = False
                self._status.start_time = None
                for ps in self._status.platforms.values():
                    ps.streaming = False
        return self._status

    def update_platform(self, platform_name: str, stream_key: str) -> None:
        """Update a platform's stream key and reconfigure its RTMP URL.

        Sets streaming=False after update so the platform must be
        re-added to an active broadcast via start_broadcast().
        """
        if platform_name not in self._status.platforms:
            return
        ps = self._status.platforms[platform_name]
        if stream_key:
            try:
                plat = Platform(platform_name)
                ps.rtmp_url = build_rtmp_url(plat, stream_key)
                ps.error = None
            except ValueError as exc:
                ps.error = str(exc)
                ps.rtmp_url = ""
        else:
            ps.rtmp_url = ""
            ps.error = "Stream key not configured"
        ps.streaming = False

    def start_broadcast(self) -> None:
        """Start the broadcast — spawns FFmpeg to multiplex to all configured platforms."""
        if self._status.active:
            logger.warning("Broadcast already active")
            return

        ready_platforms = [
            (name, ps) for name, ps in self._status.platforms.items()
            if ps.rtmp_url and not ps.error
        ]
        if not ready_platforms:
            logger.error("No platforms configured — cannot start broadcast")
            return

        # Build FFmpeg tee mux command
        # Input: listen on RTMP ingest (or read from a pipe/file for testing)
        input_url = f"rtmp://{self.settings.rtmp_ingest_host}:{self.settings.rtmp_ingest_port}/live/main"
        output_urls = [ps.rtmp_url for _, ps in ready_platforms]
        # Use tee muxer: map=0 copies video+audio to each output
        tee_output = " | ".join(
            f"[f=flv]{url}" for url in output_urls
        )
        cmd = [
            "ffmpeg",
            "-i", input_url,
            "-c", "copy",
            "-f", "tee",
            tee_output,
        ]

        logger.info("Starting broadcast with FFmpeg tee to %d platforms", len(ready_platforms))
        try:
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            self._status.active = True
            self._status.start_time = time()
            for name, ps in ready_platforms:
                ps.streaming = True
            logger.info("Broadcast started (PID %d)", self._process.pid)
        except FileNotFoundError:
            logger.error("FFmpeg not found on PATH — install FFmpeg to use streaming")
            for name, ps in ready_platforms:
                ps.error = "FFmpeg not found"
        except Exception as exc:
            logger.error("Failed to start broadcast: %s", exc)
            for name, ps in ready_platforms:
                ps.error = str(exc)

    def stop_broadcast(self) -> None:
        """Stop the broadcast and terminate FFmpeg."""
        if not self._status.active or not self._process:
            logger.warning("No active broadcast to stop")
            return

        self._process.terminate()
        try:
            self._process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self._process.kill()
            self._process.wait()

        self._status.active = False
        self._status.start_time = None
        for ps in self._status.platforms.values():
            ps.streaming = False
        self._process = None
        logger.info("Broadcast stopped")

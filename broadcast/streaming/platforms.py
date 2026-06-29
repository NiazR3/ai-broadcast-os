"""Platform definitions and RTMP URL construction."""

from dataclasses import dataclass, field
from enum import Enum
from time import time
from typing import Optional


class Platform(Enum):
    TWITCH = "twitch"
    YOUTUBE = "youtube"
    FACEBOOK = "facebook"


PLATFORM_RTMP_BASE = {
    Platform.TWITCH: "rtmp://live.twitch.tv/app",
    Platform.YOUTUBE: "rtmp://a.rtmp.youtube.com/live2",
    Platform.FACEBOOK: "rtmp://live-api-s.facebook.com:80/rtmp",
}


@dataclass
class PlatformStatus:
    """Streaming status for a single platform."""
    platform: Platform
    streaming: bool = False
    rtmp_url: str = ""
    error: Optional[str] = None


@dataclass
class BroadcastStatus:
    """Overall broadcast status."""
    active: bool = False
    start_time: Optional[float] = None  # Unix timestamp
    platforms: dict[str, PlatformStatus] = field(default_factory=dict)

    @property
    def uptime_seconds(self) -> int:
        if not self.start_time:
            return 0
        return int(time() - self.start_time)

    @property
    def all_streaming(self) -> bool:
        return all(p.streaming for p in self.platforms.values())


def build_rtmp_url(platform: Platform, stream_key: str) -> str:
    """Build the full RTMP URL for a platform using the stream key."""
    base = PLATFORM_RTMP_BASE[platform]
    if not stream_key:
        raise ValueError(f"Stream key for {platform.value} is empty")
    return f"{base}/{stream_key}"

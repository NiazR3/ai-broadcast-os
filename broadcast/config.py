from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Broadcast service configuration."""

    service_name: str = "ai-broadcast-os"
    version: str = "0.1.0"
    host: str = "0.0.0.0"
    port: int = 8100

    # OBS WebSocket
    obs_host: str = "localhost"
    obs_port: int = 4455
    obs_password: str = ""

    # RTMP ingest
    rtmp_ingest_host: str = "0.0.0.0"
    rtmp_ingest_port: int = 1935
    rtmp_output_dir: str = "/tmp/broadcast"

    # Platform stream keys (user-configured via API)
    twitch_stream_key: str = ""
    youtube_stream_key: str = ""
    facebook_stream_key: str = ""

    # Streaming endpoints (RTMP URLs)
    twitch_rtmp_url: str = "rtmp://live.twitch.tv/app"
    youtube_rtmp_url: str = "rtmp://a.rtmp.youtube.com/live2"
    facebook_rtmp_url: str = "rtmp://live-api-s.facebook.com:80/rtmp"

    # Authentication
    api_key: str = ""  # BROADCAST_API_KEY env var; empty = no auth (dev mode)

    # WebSocket origin validation -- comma-separated list of allowed origins
    # e.g. "http://localhost:5173,http://localhost:8100"
    websocket_allowed_origins: list[str] = ["http://localhost:5173"]

    model_config = {"env_prefix": "BROADCAST_", "env_file": ".env"}

    @property
    def platform_stream_keys(self) -> dict[str, str]:
        return {
            "twitch": self.twitch_stream_key,
            "youtube": self.youtube_stream_key,
            "facebook": self.facebook_stream_key,
        }

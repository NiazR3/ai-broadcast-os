"""Tests for the RTMP multiplex engine."""

from unittest.mock import patch, MagicMock
from broadcast.streaming.multiplexer import Multiplexer
from broadcast.streaming.platforms import Platform, PlatformStatus
from broadcast.config import Settings
import pytest


def test_multiplexer_initial_state():
    settings = Settings()
    mux = Multiplexer(settings)
    assert not mux.status.active
    assert mux.status.uptime_seconds == 0


def test_multiplexer_configured_platforms():
    settings = Settings(
        twitch_stream_key="live_123",
        youtube_stream_key="xxxx-yyyy",
        facebook_stream_key="fb_key_abc",
    )
    mux = Multiplexer(settings)
    assert len(mux.status.platforms) == 3
    assert mux.status.platforms["twitch"].rtmp_url == "rtmp://live.twitch.tv/app/live_123"
    assert mux.status.platforms["youtube"].rtmp_url == "rtmp://a.rtmp.youtube.com/live2/xxxx-yyyy"
    assert mux.status.platforms["facebook"].rtmp_url == "rtmp://live-api-s.facebook.com:80/rtmp/fb_key_abc"


def test_multiplexer_missing_stream_key():
    settings = Settings(
        twitch_stream_key="live_123",
        youtube_stream_key="",
        facebook_stream_key="fb_key_abc",
    )
    mux = Multiplexer(settings)
    # Missing key should still allow other platforms
    assert "youtube" in mux.status.platforms
    assert not mux.status.platforms["youtube"].streaming
    assert mux.status.platforms["youtube"].error is not None


@patch("broadcast.streaming.multiplexer.subprocess.Popen")
def test_multiplexer_start_stop(mock_popen):
    mock_process = MagicMock()
    mock_process.pid = 12345
    mock_popen.return_value = mock_process

    settings = Settings(
        twitch_stream_key="live_123",
        youtube_stream_key="xxxx-yyyy",
        facebook_stream_key="fb_key_abc",
    )
    mux = Multiplexer(settings)
    mux.start_broadcast()
    assert mux.status.active
    assert mux.status.all_streaming
    mux.stop_broadcast()
    assert not mux.status.active


@patch("broadcast.streaming.multiplexer.subprocess.Popen")
def test_multiplexer_no_platforms(mock_popen):
    settings = Settings()
    mux = Multiplexer(settings)
    mux.start_broadcast()
    # Should not try to start if no platforms are ready
    mock_popen.assert_not_called()
    assert not mux.status.active


@patch("broadcast.streaming.multiplexer.subprocess.Popen")
def test_multiplexer_ffmpeg_not_found(mock_popen):
    mock_popen.side_effect = FileNotFoundError("ffmpeg not found")

    settings = Settings(
        twitch_stream_key="live_123",
        youtube_stream_key="xxxx-yyyy",
        facebook_stream_key="fb_key_abc",
    )
    mux = Multiplexer(settings)
    mux.start_broadcast()
    # Should handle gracefully — active stays False
    assert not mux.status.active
    # All platforms should have FFmpeg error
    for ps in mux.status.platforms.values():
        assert ps.error == "FFmpeg not found"

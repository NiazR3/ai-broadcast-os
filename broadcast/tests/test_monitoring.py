"""Tests for Prometheus monitoring — metric definitions, middleware, and /metrics endpoint."""

from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient

from broadcast.main import app


def test_metrics_endpoint_returns_prometheus_text() -> None:
    """The /metrics endpoint should return Prometheus text format with registered metrics."""
    client = TestClient(app)
    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert "version=0.0.4" in resp.headers["content-type"], "Expected Prometheus text format"
    body = resp.text

    # Verify standard registered metrics are present
    assert "python_info" in body, "Default prometheus_client metrics missing"
    assert "http_requests_total" in body, "http_requests_total metric missing"
    assert "analytics_events_total" in body, "analytics_events_total metric missing"
    assert "analytics_collector_up" in body, "analytics_collector_up metric missing"
    assert "broadcast_sessions_total" in body, "broadcast_sessions_total metric missing"


def test_metrics_accessible_without_api_key() -> None:
    """The /metrics endpoint is intentionally unprotected for Prometheus scraping."""
    client = TestClient(app)
    resp = client.get("/metrics")
    assert resp.status_code == 200


def test_health_endpoint_does_not_appear_in_http_requests_total() -> None:
    """The /health endpoint should be excluded from instrumentation to avoid
    noise from load-balancer health checks.  We verify by checking that
    after a health call, no path=/health label appears in the /metrics output."""
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200

    body = client.get("/metrics").text
    assert 'path="/health"' not in body, "/health should be excluded from http_requests_total"


def test_metrics_endpoint_does_not_appear_in_http_requests_total() -> None:
    """The /metrics endpoint itself should be excluded — we don't want
    recursive instrumentation."""
    client = TestClient(app)
    # Fetch metrics a few times
    for _ in range(3):
        client.get("/metrics")

    body = client.get("/metrics").text
    assert 'path="/metrics"' not in body, "/metrics should be excluded from http_requests_total"


def test_http_request_histogram_present() -> None:
    """The http_request_duration_seconds histogram should be registered."""
    client = TestClient(app)
    body = client.get("/metrics").text
    assert "http_request_duration_seconds" in body


def test_collector_up_is_present() -> None:
    """The analytics_collector_up gauge is registered in the /metrics output."""
    client = TestClient(app)
    body = client.get("/metrics").text
    for line in body.splitlines():
        if line.startswith("analytics_collector_up"):
            # Should be a float value (0.0 or 1.0)
            parts = line.rsplit(" ", 1)
            assert len(parts) == 2, f"Could not parse: {line}"
            float(parts[1])  # raises if not a float
            break
    else:
        pytest.fail("analytics_collector_up not found in /metrics output")


def _parse_metric(body: str, name: str, labels: dict[str, str] | None = None) -> float | None:
    """Parse a single Prometheus metric value from the /metrics text response.

    Returns the float value of the first matching metric line, or ``None``.
    """
    for line in body.splitlines():
        if line.startswith("#") or not line.strip():
            continue
        # Split on { or whitespace
        if labels:
            # e.g. broadcast_sessions_total 1.0 or with labels
            for candidate in line.splitlines():
                if candidate.startswith(name):
                    # Parse label key=value pairs
                    brace = candidate.find("{")
                    if brace >= 0:
                        label_section = candidate[brace:]
                        metric_name_part = candidate[:brace]
                    else:
                        metric_name_part = candidate.split()[0]
                        label_section = ""

                    if metric_name_part.strip() != name:
                        continue

                    # Check all requested labels are present
                    all_match = True
                    for k, v in labels.items():
                        if f'{k}="{v}"' not in label_section:
                            all_match = False
                            break
                    if not all_match:
                        continue

                    # Extract the value after the last space
                    parts = candidate.rsplit(" ", 1)
                    if len(parts) == 2:
                        try:
                            return float(parts[1])
                        except ValueError:
                            continue
        else:
            if line.startswith(f"{name} "):
                parts = line.rsplit(" ", 1)
                if len(parts) == 2:
                    try:
                        return float(parts[1])
                    except ValueError:
                        continue
    return None


def test_analytics_events_metric_increments() -> None:
    """Verify that analytics_events_total increments when events are processed.

    We simulate events through the EventBus and check the /metrics endpoint.
    """
    from broadcast.analytics.database import AnalyticsDatabase
    from broadcast.analytics.session import SessionManager
    from broadcast.events.bus import EventBus
    from broadcast.analytics.collector import MetricsCollector

    db = AnalyticsDatabase(db_path=":memory:")
    event_bus = EventBus()
    session_manager = SessionManager(db)
    collector = MetricsCollector(db, event_bus, session_manager)

    # Run everything inside an async context so collector tasks fire
    async def run():
        collector.start()
        await asyncio.sleep(0.05)  # let consumer tasks subscribe
        await event_bus.publish("broadcast", {
            "type": "broadcast.started",
            "platforms": ["twitch"],
        })
        await event_bus.publish("broadcast", {
            "type": "scene.switched",
            "scene": "intro",
        })
        await asyncio.sleep(0.05)
        collector.stop()

    asyncio.run(run())

    # Check via /metrics that events were tracked
    client = TestClient(app)
    body = client.get("/metrics").text

    # broadcast.started should have been counted
    val = _parse_metric(body, "analytics_events_total", {"event_type": "broadcast.started"})
    assert val is not None and val >= 1.0, (
        f"Expected analytics_events_total{{event_type='broadcast.started'}} >= 1, got {val}"
    )

    # scene.switched should have been counted
    val = _parse_metric(body, "analytics_events_total", {"event_type": "scene.switched"})
    assert val is not None and val >= 1.0, (
        f"Expected analytics_events_total{{event_type='scene.switched'}} >= 1, got {val}"
    )

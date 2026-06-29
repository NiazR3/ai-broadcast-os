"""Prometheus metric definitions for the Broadcast OS.

All counters, gauges, and histograms are registered here so the
``/metrics`` endpoint (mounted via ``make_asgi_app()``) serves them.

Import these from application code to record business-level metrics:
    from broadcast.monitoring.metrics import broadcast_sessions_total

For HTTP request metrics, use the ``PrometheusMiddleware`` in this module.
"""

from __future__ import annotations

import time
from typing import Awaitable, Callable

from prometheus_client import Counter, Gauge, Histogram, make_asgi_app
from starlette.requests import Request
from starlette.responses import Response

# ── HTTP request metrics ────────────────────────────────────────────

http_requests_total = Counter(
    "http_requests_total",
    "Total HTTP requests by method, path, and response status",
    ["method", "path", "status"],
)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "path"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)


# ── Broadcast lifecycle metrics ─────────────────────────────────────

broadcast_sessions_total = Counter(
    "broadcast_sessions_total",
    "Total broadcast sessions created",
)

broadcast_sessions_active = Gauge(
    "broadcast_sessions_active",
    "Currently active broadcast sessions",
)

broadcast_duration_seconds = Histogram(
    "broadcast_duration_seconds",
    "Histogram of broadcast session durations (ended sessions only)",
    buckets=(10, 30, 60, 120, 300, 600, 1800, 3600),
)


# ── Analytics / collector metrics ───────────────────────────────────

analytics_events_total = Counter(
    "analytics_events_total",
    "Total analytics events processed by event type",
    ["event_type"],
)

analytics_chat_messages_total = Counter(
    "analytics_chat_messages_total",
    "Total chat messages recorded by the analytics collector",
)

analytics_snapshots_total = Counter(
    "analytics_snapshots_total",
    "Total metrics snapshots taken",
)

analytics_collector_up = Gauge(
    "analytics_collector_up",
    "Whether the metrics collector is running (1 = running, 0 = stopped)",
)


# ── Metrics ASGI app (mounted at /metrics) ──────────────────────────

# Pre-built ASGI app that serves /metrics in Prometheus text format.
# It picks up all metrics registered with the default registry.
metrics_asgi_app = make_asgi_app()


# ── HTTP metrics middleware ─────────────────────────────────────────

# Paths to exclude from HTTP instrumentation.
_SKIP_PATHS = frozenset({"/metrics", "/health"})


class PrometheusMiddleware:
    """FastAPI / Starlette middleware that records HTTP request metrics.

    Usage::

        app.add_middleware(PrometheusMiddleware)
    """

    def __init__(self, app: Callable[..., Awaitable[Response]]) -> None:
        self.app = app

    async def __call__(self, scope: dict, receive: Callable, send: Callable) -> None:
        """ASGI call — wraps send to capture status code and duration."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if path in _SKIP_PATHS:
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "UNKNOWN")
        start = time.monotonic()
        status_code = [None]  # mutable cell for closure

        async def send_wrapper(message: dict) -> None:
            if message["type"] == "http.response.start":
                status_code[0] = message["status"]
            await send(message)

        await self.app(scope, receive, send_wrapper)

        duration = time.monotonic() - start
        status = status_code[0] if status_code[0] is not None else 0

        http_requests_total.labels(method=method, path=path, status=str(status)).inc()
        http_request_duration_seconds.labels(method=method, path=path).observe(duration)

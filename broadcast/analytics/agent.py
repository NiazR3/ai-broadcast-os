"""Analytics Agent — owns database, collector, session manager, and report generator."""

from __future__ import annotations

import logging
import os
from typing import Optional

from broadcast.agents.base import BaseAgent
from broadcast.analytics.collector import MetricsCollector
from broadcast.analytics.database import AnalyticsDatabase
from broadcast.analytics.reporting import ReportGenerator
from broadcast.analytics.session import SessionManager
from broadcast.events.bus import EventBus

logger = logging.getLogger(__name__)


class AnalyticsAgent(BaseAgent):
    """Agent that manages the analytics suite — metrics, sessions, and reports."""

    def __init__(
        self,
        db_path: Optional[str] = None,
        event_bus: Optional[EventBus] = None,
    ) -> None:
        super().__init__()
        self._db = AnalyticsDatabase(db_path=db_path)
        self._event_bus = event_bus or EventBus()
        self._session_manager = SessionManager(self._db)
        self._collector = MetricsCollector(self._db, self._event_bus, self._session_manager)
        self._report_generator = ReportGenerator(self._db)

    @property
    def agent_name(self) -> str:
        return "Analytics"

    @property
    def agent_type(self) -> str:
        return "analytics"

    @property
    def db(self) -> AnalyticsDatabase:
        return self._db

    @property
    def session_manager(self) -> SessionManager:
        return self._session_manager

    @property
    def collector(self) -> MetricsCollector:
        return self._collector

    @property
    def report_generator(self) -> ReportGenerator:
        return self._report_generator

    def start(self) -> None:
        """Start the analytics agent and metrics collector."""
        super().start()
        self._collector.start()

    def stop(self) -> None:
        """Stop the metrics collector and agent."""
        self._collector.stop()
        super().stop()

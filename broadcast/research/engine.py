"""Research engine — pluggable backends, topic extraction, and agent."""

from __future__ import annotations

import abc
import asyncio
import logging
import threading
from time import time
from typing import Optional

from broadcast.agents.base import BaseAgent
from broadcast.events.bus import EventBus
from broadcast.research.models import (
    FactCheck,
    ResearchResult,
    ResearchStatus,
    ResearchTopic,
    SourceCitation,
)

logger = logging.getLogger(__name__)


# ── Research Backend ────────────────────────────────────────────────

class ResearchBackend(abc.ABC):
    """Abstract base for pluggable research backends."""

    @abc.abstractmethod
    def research(self, topic: ResearchTopic) -> ResearchResult:
        """Perform research on a topic and return structured results."""

    @abc.abstractmethod
    def supports_topic(self, topic: str) -> bool:
        """Return True if this backend can handle the given topic."""


RESEARCH_TEMPLATES: dict[str, dict] = {
    "technology": {
        "summary": (
            "The technology sector continues to advance rapidly with breakthroughs in "
            "artificial intelligence, cloud computing, and semiconductor design. "
            "Major tech companies are investing heavily in next-generation processors "
            "and AI-powered applications."
        ),
        "key_points": [
            "AI chip market expected to reach $400B by 2030",
            "Cloud infrastructure spending grew 22% year-over-year",
            "Open-source AI models are democratizing access to machine learning",
        ],
        "sources": [
            {"url": "https://example.com/tech-report-2026", "title": "Global Tech Outlook 2026", "snippet": "Comprehensive analysis of technology trends and market projections.", "relevance_score": 0.95},
            {"url": "https://example.com/ai-semiconductors", "title": "AI Semiconductor Landscape", "snippet": "Deep dive into AI chip manufacturers and emerging architectures.", "relevance_score": 0.88},
        ],
        "fact_checks": [
            {"claim": "AI will replace all software engineers by 2030", "verdict": "contradicted", "explanation": "Industry experts predict AI will augment rather than replace software engineers, with demand for developers remaining strong."},
        ],
    },
    "weather": {
        "summary": (
            "Current weather patterns show significant variability across regions, "
            "with climate change contributing to more frequent extreme weather events. "
            "Temperatures are running above historical averages in most areas."
        ),
        "key_points": [
            "Global average temperature 1.3°C above pre-industrial levels",
            "Extreme weather events increased 35% over the past decade",
            "Renewable energy now accounts for 30% of global electricity generation",
        ],
        "sources": [
            {"url": "https://example.com/climate-report", "title": "Annual Climate Assessment", "snippet": "NOAA's comprehensive climate data analysis for the current year.", "relevance_score": 0.92},
            {"url": "https://example.com/weather-patterns", "title": "Global Weather Patterns Study", "snippet": "Research on shifting weather patterns and their regional impacts.", "relevance_score": 0.85},
        ],
        "fact_checks": [
            {"claim": "2025 was the hottest year on record", "verdict": "supported", "explanation": "NOAA and NASA confirmed 2025 tied with 2024 as the warmest year since global records began."},
        ],
    },
    "sports": {
        "summary": (
            "The sports world is seeing major developments across leagues, with "
            "record-breaking performances, emerging talent, and evolving fan "
            "engagement through digital platforms and streaming services."
        ),
        "key_points": [
            "Streaming viewership surpassed traditional broadcast for major events",
            "Esports continues to gain mainstream recognition and investment",
            "Athlete wellness and mental health initiatives are becoming league priorities",
        ],
        "sources": [
            {"url": "https://example.com/sports-trends", "title": "Sports Industry Report", "snippet": "Annual analysis of sports viewership, revenue, and participation trends.", "relevance_score": 0.90},
            {"url": "https://example.com/esports-growth", "title": "Esports Market Analysis", "snippet": "Growth metrics and demographic shifts in competitive gaming viewership.", "relevance_score": 0.82},
        ],
        "fact_checks": [
            {"claim": "Esports viewership now exceeds traditional sports among under-25s", "verdict": "supported", "explanation": "Multiple market research firms report esports viewership surpassing traditional sports in the 18-24 demographic."},
        ],
    },
    "entertainment": {
        "summary": (
            "The entertainment industry continues its transformation with streaming "
            "services dominating content consumption, while theatrical releases "
            "and live events see strong post-pandemic recovery."
        ),
        "key_points": [
            "Global streaming market valued at $250B with 12% annual growth",
            "AI-generated content is creating new creative workflows in production",
            "Interactive and immersive experiences are driving audience engagement",
        ],
        "sources": [
            {"url": "https://example.com/entertainment-report", "title": "Entertainment Industry Outlook", "snippet": "Comprehensive analysis of entertainment consumption trends and forecasts.", "relevance_score": 0.91},
            {"url": "https://example.com/streaming-wars", "title": "Streaming Landscape 2026", "snippet": "Competitive analysis of major streaming platforms and market share.", "relevance_score": 0.84},
        ],
        "fact_checks": [
            {"claim": "Traditional cable TV will be obsolete by 2027", "verdict": "unverified", "explanation": "While cord-cutting continues accelerating, most analysts predict a gradual decline rather than complete obsolescence by 2027."},
        ],
    },
    "science": {
        "summary": (
            "Scientific research is pushing boundaries across multiple frontiers, "
            "from quantum computing milestones to breakthroughs in fusion energy "
            "and biotechnology advances that promise to transform medicine."
        ),
        "key_points": [
            "First practical quantum error correction demonstrated at scale",
            "Nuclear fusion energy record broken — 15 seconds of sustained reaction",
            "mRNA platform technology being adapted for cancer and autoimmune treatments",
        ],
        "sources": [
            {"url": "https://example.com/science-breakthroughs", "title": "Top Science Breakthroughs 2026", "snippet": "Curated list of the most significant scientific achievements of the year.", "relevance_score": 0.93},
            {"url": "https://example.com/quantum-progress", "title": "Quantum Computing Roadmap", "snippet": "Current state of quantum computing development and near-term milestones.", "relevance_score": 0.87},
        ],
        "fact_checks": [
            {"claim": "Quantum computers will break all encryption by 2030", "verdict": "contradicted", "explanation": "Current estimates suggest cryptographically-relevant quantum computers remain 10-15 years away, with post-quantum cryptography standards being developed now."},
        ],
    },
    "health": {
        "summary": (
            "Healthcare is undergoing rapid transformation through digital health "
            "innovations, personalized medicine approaches, and breakthroughs in "
            "treatment modalities for chronic and acute conditions."
        ),
        "key_points": [
            "AI-assisted diagnostics improving accuracy by 40% in radiology",
            "Gene therapy approvals expanding to common conditions",
            "Digital therapeutics market growing at 25% CAGR through 2030",
        ],
        "sources": [
            {"url": "https://example.com/health-tech", "title": "Digital Health Transformation", "snippet": "Analysis of technology adoption trends across healthcare systems worldwide.", "relevance_score": 0.89},
            {"url": "https://example.com/gene-therapy", "title": "Gene Therapy Advances", "snippet": "Overview of FDA-approved gene therapies and pipeline candidates.", "relevance_score": 0.83},
        ],
        "fact_checks": [
            {"claim": "AI will replace doctors within a decade", "verdict": "contradicted", "explanation": "AI systems augment diagnostic capabilities but still require physician oversight for clinical decision-making and patient care."},
        ],
    },
    "business": {
        "summary": (
            "The global business landscape is adapting to remote work permanence, "
            "supply chain restructuring, and the integration of AI across operations. "
            "Startup funding has shifted toward sustainable and deep-tech ventures."
        ),
        "key_points": [
            "Remote and hybrid work now standard for 65% of knowledge workers",
            "Supply chain nearshoring investments reached $180B globally",
            "AI startups captured 40% of all venture capital funding this quarter",
        ],
        "sources": [
            {"url": "https://example.com/business-outlook", "title": "Global Business Trends", "snippet": "Quarterly analysis of business environment, investment trends, and economic indicators.", "relevance_score": 0.88},
            {"url": "https://example.com/venture-capital", "title": "Venture Capital Report", "snippet": "Detailed breakdown of VC investment by sector, stage, and geography.", "relevance_score": 0.81},
        ],
        "fact_checks": [
            {"claim": "Remote work reduces productivity by 20%", "verdict": "contradicted", "explanation": "Comprehensive studies show remote workers are equally or more productive, though collaboration and innovation metrics require intentional management."},
        ],
    },
    "politics": {
        "summary": (
            "Political landscapes worldwide are shaped by economic pressures, "
            "technological regulation debates, and shifting voter demographics. "
            "Digital governance and AI policy are emerging as key electoral issues."
        ),
        "key_points": [
            "AI regulation frameworks being developed in 40+ countries",
            "Youth voter turnout reached record levels in recent elections",
            "Digital sovereignty and data localization laws expanding globally",
        ],
        "sources": [
            {"url": "https://example.com/political-analysis", "title": "Global Political Landscape", "snippet": "Analysis of political trends, policy developments, and electoral dynamics worldwide.", "relevance_score": 0.86},
            {"url": "https://example.com/ai-policy", "title": "AI Governance Tracker", "snippet": "Comprehensive tracking of AI policy developments across major economies.", "relevance_score": 0.79},
        ],
        "fact_checks": [
            {"claim": "AI-generated disinformation swung the last election", "verdict": "unverified", "explanation": "While AI-generated content is a growing concern, attributing election outcomes to any single factor oversimplifies complex voter behavior."},
        ],
    },
    "general": {
        "summary": (
            "Here's a summary of current events and trending topics. The information "
            "landscape continues to evolve with new developments across multiple "
            "domains that may be relevant to your broadcast segment."
        ),
        "key_points": [
            "Multiple significant developments across various sectors",
            "Public interest in the topic is trending upward",
            "Expert opinions vary on the long-term implications",
        ],
        "sources": [
            {"url": "https://example.com/news-summary", "title": "Today's News Summary", "snippet": "Curated overview of major news stories and developments.", "relevance_score": 0.75},
        ],
        "fact_checks": [
            {"claim": "This topic requires more specific research", "verdict": "unverified", "explanation": "Our research indicates this general topic would benefit from a more specific query to provide authoritative fact-checking."},
        ],
    },
}

DEFAULT_TEMPLATE = RESEARCH_TEMPLATES["general"]


class MockResearchBackend(ResearchBackend):
    """Returns template-based research results keyed to topic keywords."""

    def __init__(self) -> None:
        self._id_counter: int = 0

    def supports_topic(self, topic: str) -> bool:
        lowered = topic.lower()
        return any(kw in lowered for kw in RESEARCH_TEMPLATES)

    def research(self, topic: ResearchTopic) -> ResearchResult:
        lowered = topic.query.lower()
        for keyword, template in RESEARCH_TEMPLATES.items():
            if keyword in lowered:
                return self._build_result(topic.id, template, topic.created_at)
        return self._build_result(topic.id, DEFAULT_TEMPLATE, topic.created_at)

    def _build_result(self, topic_id: str, template: dict, created_at: float) -> ResearchResult:
        self._id_counter += 1
        return ResearchResult(
            id=f"result_{topic_id}_{int(time() * 1000)}_{self._id_counter}",
            topic_id=topic_id,
            summary=template["summary"],
            key_points=list(template["key_points"]),
            sources=[SourceCitation(**s) for s in template["sources"]],
            fact_checks=[FactCheck(**f) for f in template["fact_checks"]],
            created_at=created_at,
        )


# ── Research Engine ─────────────────────────────────────────────────

class ResearchEngine:
    """Manages research lifecycle — submit, store, retrieve results."""

    def __init__(self) -> None:
        self._results: dict[str, ResearchResult] = {}
        self._topics: dict[str, ResearchTopic] = {}
        self._id_counter: int = 0
        self._lock: threading.Lock = threading.Lock()

    def _next_id(self) -> str:
        """Generate a unique topic ID using timestamp and counter."""
        with self._lock:
            self._id_counter += 1
            return f"topic_{int(time() * 1000)}_{self._id_counter}"

    def submit(self, topic: ResearchTopic, backend: ResearchBackend) -> str:
        """Submit a topic for research and return the result ID.

        With the mock backend this resolves synchronously; a real backend
        would queue for async resolution.
        """
        topic.status = ResearchStatus.IN_PROGRESS
        result = backend.research(topic)
        topic.status = ResearchStatus.COMPLETE
        topic.completed_at = time()
        self._topics[topic.id] = topic
        self._results[result.id] = result
        return result.id

    def get(self, result_id: str) -> Optional[ResearchResult]:
        """Get a research result by ID."""
        return self._results.get(result_id)

    def list(self, limit: int = 10) -> list[ResearchResult]:
        """List the most recent research results."""
        sorted_results = sorted(
            self._results.values(),
            key=lambda r: r.created_at,
            reverse=True,
        )
        return sorted_results[:limit]

    def extract_topics(self, text: str) -> list[str]:
        """Extract potential research topics from text.

        Uses simple keyword matching against known template categories.
        """
        lowered = text.lower()
        found: list[str] = []
        for keyword in RESEARCH_TEMPLATES:
            if keyword in lowered:
                found.append(keyword)
        return found


# ── Research Agent ──────────────────────────────────────────────────

class ResearchAgent(BaseAgent):
    """Agent that manages research lifecycle and integrates with EventBus."""

    def __init__(self, event_bus: Optional[EventBus] = None) -> None:
        super().__init__()
        self._engine = ResearchEngine()
        self._backend = MockResearchBackend()
        self._event_bus = event_bus or EventBus()

    @property
    def agent_name(self) -> str:
        return "Research"

    @property
    def agent_type(self) -> str:
        return "research"

    @property
    def engine(self) -> ResearchEngine:
        return self._engine

    def submit_research(self, query: str, segment_id: str = "", segment_title: str = "", context: str = "") -> dict:
        """Submit a research topic and return the result."""
        topic = ResearchTopic(
            id=self._engine._next_id(),
            query=query,
            segment_id=segment_id,
            segment_title=segment_title,
            context=context,
            created_at=time(),
        )
        result_id = self._engine.submit(topic, self._backend)
        result = self._engine.get(result_id)
        # Publish to EventBus
        payload = {
            "type": "research.result.ready",
            "topic_id": topic.id,
            "result_id": result_id,
            "query": query,
            "timestamp": time(),
        }
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            asyncio.run(self._event_bus.publish("research", payload))
        else:
            loop.create_task(self._event_bus.publish("research", payload))
        return result.model_dump() if result else {}

    def get_result(self, result_id: str) -> Optional[ResearchResult]:
        """Get a specific research result."""
        return self._engine.get(result_id)

    def list_results(self, limit: int = 10) -> list[ResearchResult]:
        """List recent research results."""
        return self._engine.list(limit)

    def extract_topics(self, text: str) -> list[str]:
        """Extract research topics from text."""
        return self._engine.extract_topics(text)

    def get_context_for_segment(self, segment_id: str) -> Optional[str]:
        """Get a formatted research summary for dialogue injection.

        Looks up the most recent result associated with the given segment.
        Returns None if no research is available.
        """
        for result in reversed(list(self._engine._results.values())):
            topic = self._engine._topics.get(result.topic_id)
            if topic and topic.segment_id == segment_id:
                return (
                    f"Research summary: {result.summary}\n"
                    f"Key points: {'; '.join(result.key_points)}"
                )
        return None

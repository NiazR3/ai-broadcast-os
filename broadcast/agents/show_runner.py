"""ShowRunnerAgent — orchestrates full episode production pipeline.

Coordinates Producer, Director, Host, CoHost, Research, Media, Poll,
and OBS modules into a single automated show production workflow.
"""

from __future__ import annotations

import asyncio
import logging
from enum import Enum
from time import time
from typing import Optional

from broadcast.agents.base import BaseAgent
from broadcast.agents.dialogue import HostAgent, CoHostAgent
from broadcast.agents.director import DirectorAgent
from broadcast.agents.models import (
    AgentType,
    EpisodeScript,
    ScriptStatus,
    Segment,
    SegmentType,
)
from broadcast.agents.persona import PersonaProfile, PersonaRepository, VoiceStyle
from broadcast.agents.producer import ProducerAgent
from broadcast.audience.polls import PollEngine
from broadcast.config import Settings
from broadcast.events.bus import EventBus
from broadcast.media.engine import MediaAgent
from broadcast.media.models import ChartConfig, ChartType, TextOverlayConfig
from broadcast.obs.controller import ObsController
from broadcast.research.engine import ResearchAgent

logger = logging.getLogger(__name__)


class ShowState(str, Enum):
    """Lifecycle states of a show production."""
    IDLE = "idle"
    PRODUCING = "producing"
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


# ── Segment templates (6-segment show structure) ────────────────────────

SEGMENT_TEMPLATES: list[dict] = [
    {
        "id": "intro",
        "type": SegmentType.INTRO,
        "duration_seconds": 30,
        "scene_name": "Intro",
    },
    {
        "id": "content_1",
        "type": SegmentType.CONTENT,
        "duration_seconds": 180,
        "scene_name": "Content",
    },
    {
        "id": "guest",
        "type": SegmentType.GUEST,
        "duration_seconds": 120,
        "scene_name": "Guest",
    },
    {
        "id": "ad",
        "type": SegmentType.AD,
        "duration_seconds": 30,
        "scene_name": "Ad",
    },
    {
        "id": "content_2",
        "type": SegmentType.CONTENT,
        "duration_seconds": 120,
        "scene_name": "Content",
    },
    {
        "id": "outro",
        "type": SegmentType.OUTRO,
        "duration_seconds": 30,
        "scene_name": "Outro",
    },
]


# ── Topic → Poll templates ──────────────────────────────────────────────

POLL_TEMPLATES: dict[str, tuple[str, list[str]]] = {
    "technology": (
        "Which AI advancement excites you most?",
        ["Large Language Models", "Computer Vision", "Robotics", "AI in Healthcare"],
    ),
    "weather": (
        "How concerned are you about climate change?",
        ["Very concerned", "Somewhat concerned", "Not very concerned", "Not at all"],
    ),
    "sports": (
        "What's the most exciting sport to watch?",
        ["Football", "Basketball", "Esports", "Soccer"],
    ),
    "entertainment": (
        "How do you prefer to watch content?",
        ["Streaming services", "Theatrical release", "Social media", "Traditional TV"],
    ),
    "science": (
        "Which scientific field interests you most?",
        ["Space exploration", "Medicine", "Quantum computing", "Climate science"],
    ),
    "health": (
        "What health tech are you most excited about?",
        ["Wearable devices", "Telemedicine", "Gene therapy", "AI diagnostics"],
    ),
    "business": (
        "What's the biggest business trend right now?",
        ["Remote work", "AI integration", "Sustainable business", "Cryptocurrency"],
    ),
    "politics": (
        "What issue matters most to you?",
        ["Economy", "Healthcare", "Education", "Climate policy"],
    ),
}

DEFAULT_POLL: tuple[str, list[str]] = (
    "What do you think about today's topic?",
    ["Love it!", "Interesting", "Neutral", "Not for me"],
)


# ── Topic → VoiceStyle suggestions for persona matching ─────────────────

TOPIC_PERSONA_MAP: dict[str, tuple[VoiceStyle, VoiceStyle]] = {
    "technology": (VoiceStyle.WITTY, VoiceStyle.PROFESSIONAL),
    "weather": (VoiceStyle.PROFESSIONAL, VoiceStyle.CALM),
    "sports": (VoiceStyle.ENERGETIC, VoiceStyle.CASUAL),
    "entertainment": (VoiceStyle.CASUAL, VoiceStyle.WITTY),
    "science": (VoiceStyle.PROFESSIONAL, VoiceStyle.CASUAL),
    "health": (VoiceStyle.CALM, VoiceStyle.PROFESSIONAL),
    "business": (VoiceStyle.PROFESSIONAL, VoiceStyle.SERIOUS),
    "politics": (VoiceStyle.SERIOUS, VoiceStyle.PROFESSIONAL),
}


# ── Topic → chart data templates ────────────────────────────────────────

TOPIC_CHART_TEMPLATES: dict[str, dict] = {
    "technology": {
        "chart_type": ChartType.BAR,
        "title": "AI Market Growth ($B)",
        "labels": ["2022", "2023", "2024", "2025", "2026"],
        "datasets": [{"label": "AI Market", "values": [87, 136, 196, 280, 400]}],
    },
    "weather": {
        "chart_type": ChartType.LINE,
        "title": "Global Temperature Anomaly (°C)",
        "labels": ["2016", "2018", "2020", "2022", "2024", "2026"],
        "datasets": [{"label": "Anomaly", "values": [0.8, 0.9, 1.1, 1.2, 1.3, 1.4]}],
    },
    "sports": {
        "chart_type": ChartType.PIE,
        "title": "Sports Viewership Share",
        "labels": ["Streaming", "Broadcast TV", "In-Person", "Social Media"],
        "datasets": [{"label": "Share", "values": [42, 28, 15, 15]}],
    },
    "entertainment": {
        "chart_type": ChartType.BAR,
        "title": "Streaming Revenue ($B)",
        "labels": ["Netflix", "Disney+", "Amazon", "Apple", "Others"],
        "datasets": [{"label": "Revenue", "values": [35, 22, 18, 10, 15]}],
    },
    "science": {
        "chart_type": ChartType.BAR,
        "title": "R&D Investment by Field ($B)",
        "labels": ["AI", "Biotech", "Energy", "Space", "Quantum"],
        "datasets": [{"label": "Investment", "values": [150, 90, 70, 45, 25]}],
    },
    "health": {
        "chart_type": ChartType.LINE,
        "title": "Digital Health Market ($B)",
        "labels": ["2021", "2022", "2023", "2024", "2025", "2026"],
        "datasets": [{"label": "Market Size", "values": [145, 175, 210, 260, 325, 400]}],
    },
    "business": {
        "chart_type": ChartType.PIE,
        "title": "Venture Capital by Sector",
        "labels": ["AI", "Fintech", "Health", "Climate", "Other"],
        "datasets": [{"label": "Share", "values": [40, 18, 15, 12, 15]}],
    },
    "politics": {
        "chart_type": ChartType.BAR,
        "title": "Voter Turnout by Age Group",
        "labels": ["18-24", "25-34", "35-44", "45-54", "55+"],
        "datasets": [{"label": "Turnout %", "values": [55, 62, 68, 72, 78]}],
    },
}


class ShowRunnerAgent(BaseAgent):
    """Orchestrator that automates full episode production.

    Coordinates: episode creation, segment building, persona assignment,
    research, polls, media assets, dialogue generation, OBS scene
    management, and live playback control.
    """

    def __init__(
        self,
        producer: Optional[ProducerAgent] = None,
        director: Optional[DirectorAgent] = None,
        host: Optional[HostAgent] = None,
        cohost: Optional[CoHostAgent] = None,
        persona_repo: Optional[PersonaRepository] = None,
        research_agent: Optional[ResearchAgent] = None,
        media_agent: Optional[MediaAgent] = None,
        poll_engine: Optional[PollEngine] = None,
        obs: Optional[ObsController] = None,
        event_bus: Optional[EventBus] = None,
        settings: Optional[Settings] = None,
    ) -> None:
        super().__init__()
        self._producer = producer or ProducerAgent()
        self._director = director or DirectorAgent()
        self._host = host or HostAgent()
        self._cohost = cohost or CoHostAgent()
        self._persona_repo = persona_repo or PersonaRepository()
        self._research = research_agent or ResearchAgent(event_bus)
        self._media = media_agent or MediaAgent(event_bus)
        self._polls = poll_engine or PollEngine()
        self._obs = obs
        self._event_bus = event_bus or EventBus()
        self._settings = settings or Settings()

        # Show production state
        self._state: ShowState = ShowState.IDLE
        self._current_episode: Optional[EpisodeScript] = None
        self._asset_ids: list[str] = []
        self._research_ids: list[str] = []
        self._poll_id: Optional[str] = None
        self._dialogue: dict[str, dict] = {}
        self._error: Optional[str] = None

    # ── Agent identity ──────────────────────────────────────────────────

    @property
    def agent_name(self) -> str:
        return "ShowRunner"

    @property
    def agent_type(self) -> str:
        return "show_runner"

    @property
    def state(self) -> ShowState:
        return self._state

    @property
    def current_episode(self) -> Optional[EpisodeScript]:
        return self._current_episode

    # ── Public API ──────────────────────────────────────────────────────

    def produce_show(self, topic: str, category: str = "general") -> dict:
        """Orchestrate full episode production.

        Creates an episode with 6 segments, assigns topic-appropriate
        personas, submits research, creates a poll, generates media
        assets (charts, overlays), and generates host+co-host dialogue
        for every segment.

        Args:
            topic: The show topic (e.g. 'The Rise of AI in Healthcare').
            category: Topic category for template selection
                      (technology, science, sports, etc.).

        Returns:
            Dict with episode_id, status, and production summary, or an
            error dict when production cannot start or fails mid-way.
        """
        topic = topic.strip()
        if not topic:
            return {"error": "Topic is required", "state": self._state.value}

        if self._state not in (ShowState.IDLE, ShowState.COMPLETED):
            return {
                "error": f"ShowRunner is in state '{self._state.value}'. Reset the runner first.",
                "state": self._state.value,
            }

        self._state = ShowState.PRODUCING
        self._error = None
        self._asset_ids = []
        self._research_ids = []
        self._poll_id = None
        self._dialogue = {}
        category = category.lower()

        start_time = time()
        production_log: list[str] = []

        try:
            # 1. Create episode
            episode = self._producer.create_episode(topic)
            self._current_episode = episode
            production_log.append(f"Episode created: '{topic}' ({episode.id})")

            # 2. Build segments from templates
            for tmpl in SEGMENT_TEMPLATES:
                segment = Segment(
                    id=tmpl["id"],
                    type=tmpl["type"],
                    title=self._segment_title_for(tmpl["id"], topic),
                    duration_seconds=tmpl["duration_seconds"],
                    scene_name=tmpl["scene_name"],
                    dialogue_prompt=self._segment_prompt_for(tmpl["id"], topic, category),
                )
                self._producer.add_segment(episode, segment)
            production_log.append(f"6 segments created for '{topic}'")

            # 3. Assign personas based on category
            host_persona = self._find_matching_persona(AgentType.HOST, category)
            cohost_persona = self._find_matching_persona(AgentType.COHOST, category)
            if host_persona:
                self._host.assign_persona(host_persona.id, self._persona_repo)
                production_log.append(f"Host persona: '{host_persona.name}'")
            if cohost_persona:
                self._cohost.assign_persona(cohost_persona.id, self._persona_repo)
                production_log.append(f"Co-host persona: '{cohost_persona.name}'")

            # 4. Submit research
            self._research_ids = self._submit_topic_research(topic, category)
            production_log.append(f"Research: {len(self._research_ids)} submission(s)")

            # 5. Create poll
            poll = self._create_topic_poll(category)
            if poll:
                self._poll_id = poll.id
                production_log.append(f"Poll created: '{poll.question}'")

            # 6. Generate media assets
            asset_count = self._generate_show_assets(category, topic)
            production_log.append(f"Media assets: {asset_count} created")

            # 7. Generate dialogue for all segments
            for seg in episode.segments:
                host_block = self._host.generate_dialogue(seg, repo=self._persona_repo)
                host_text = host_block.lines[0].text if host_block.lines else ""
                cohost_block = self._cohost.generate_dialogue(
                    seg, host_dialogue=host_text, repo=self._persona_repo
                )
                self._dialogue[seg.id] = {
                    "host": host_block.model_dump(),
                    "cohost": cohost_block.model_dump(),
                }
            production_log.append(
                f"Dialogue generated for {len(episode.segments)} segments"
            )

            # Mark episode ready
            episode.status = ScriptStatus.READY
            self._state = ShowState.READY

            self._publish_event(
                "show.produced",
                episode_id=episode.id,
                topic=topic,
                category=category,
                duration_seconds=episode.total_duration,
                production_time=time() - start_time,
            )

            return {
                "episode_id": episode.id,
                "topic": topic,
                "category": category,
                "state": self._state.value,
                "segments": len(episode.segments),
                "total_duration_seconds": episode.total_duration,
                "personas": {
                    "host": host_persona.name if host_persona else None,
                    "cohost": cohost_persona.name if cohost_persona else None,
                },
                "research_count": len(self._research_ids),
                "poll_id": self._poll_id,
                "assets_created": len(self._asset_ids),
                "dialogue_generated": len(self._dialogue),
                "production_log": production_log,
                "production_time_seconds": round(time() - start_time, 2),
            }

        except Exception as exc:
            self._state = ShowState.FAILED
            self._error = str(exc)
            logger.exception("Show production failed for topic '%s'", topic)
            self._publish_event("show.failed", topic=topic, error=str(exc))
            return {
                "error": f"Production failed: {exc}",
                "state": self._state.value,
                "production_log": production_log,
            }

    async def run_show(self, episode_id: Optional[str] = None) -> dict:
        """Run a produced show — advance through segments with OBS scene switching.

        Loads the produced episode into the Director, then steps through
        every segment, returning the full playback plan with dialogue.
        Attempts OBS scene switching per segment if an ObsController was
        configured; OBS connection failures are non-fatal.

        Args:
            episode_id: Optional episode ID. Uses the current episode if
                        omitted.

        Returns:
            Dict with segment_results (dialogue per segment) and
            run_log, or an error dict.
        """
        if self._state != ShowState.READY:
            return {
                "error": f"Show must be in 'ready' state, currently '{self._state.value}'",
                "state": self._state.value,
            }

        episode = self._current_episode
        if episode is None:
            return {"error": "No episode loaded", "state": self._state.value}

        if episode_id and episode.id != episode_id:
            return {
                "error": f"Episode '{episode_id}' not found",
                "state": self._state.value,
            }

        if not episode.segments:
            return {"error": "Episode has no segments", "state": self._state.value}

        self._state = ShowState.RUNNING
        episode.status = ScriptStatus.BROADCASTING
        self._director.load_script(episode)

        run_log: list[str] = []
        segment_results: list[dict] = []

        # Try OBS connection (non-fatal if unavailable)
        obs_ready = await self._try_obs_connect()

        try:
            while self._director.has_more:
                segment = self._director.next_segment()
                if segment is None:
                    break

                # Switch OBS scene if connected
                if obs_ready and segment.scene_name:
                    switched = await self._try_obs_scene_switch(segment.scene_name)
                    if switched:
                        run_log.append(f"Scene switched: '{segment.scene_name}'")

                seg_dialogue = self._dialogue.get(segment.id, {})
                seg_result = {
                    "segment_id": segment.id,
                    "segment_type": segment.type.value,
                    "segment_title": segment.title,
                    "scene": segment.scene_name,
                    "duration_seconds": segment.duration_seconds,
                    "order": segment.order,
                    "host_dialogue": seg_dialogue.get("host", {}).get("lines", []),
                    "cohost_dialogue": seg_dialogue.get("cohost", {}).get("lines", []),
                }
                segment_results.append(seg_result)
                run_log.append(f"Segment {segment.order + 1}: '{segment.title}' ({segment.type.value})")

            episode.status = ScriptStatus.COMPLETED
            self._state = ShowState.COMPLETED

            self._publish_event("show.completed", episode_id=episode.id)

            return {
                "episode_id": episode.id,
                "state": self._state.value,
                "total_segments": len(segment_results),
                "segment_results": segment_results,
                "run_log": run_log,
            }

        except Exception as exc:
            self._state = ShowState.FAILED
            self._error = str(exc)
            logger.exception("Show run failed for episode '%s'", episode.id)
            self._publish_event("show.failed", episode_id=episode.id, error=str(exc))
            return {
                "error": f"Show run failed: {exc}",
                "state": self._state.value,
                "segment_results": segment_results,
                "run_log": run_log,
            }

    def get_show_status(self) -> dict:
        """Return the full status of the current show production."""
        return {
            "state": self._state.value,
            "error": self._error,
            "episode": self._current_episode.model_dump() if self._current_episode else None,
            "assets": list(self._asset_ids),
            "research_results": list(self._research_ids),
            "poll_id": self._poll_id,
            "dialogue_segments": list(self._dialogue.keys()),
            "personas": {
                "host": getattr(self._host, "_persona_id", None),
                "cohost": getattr(self._cohost, "_persona_id", None),
            },
        }

    def reset(self) -> None:
        """Reset the ShowRunner to idle state and clear all production data."""
        self._state = ShowState.IDLE
        self._current_episode = None
        self._asset_ids = []
        self._research_ids = []
        self._poll_id = None
        self._dialogue = {}
        self._error = None
        self._director.reset()
        self._publish_event("show.reset")

    # ── Internal helpers ────────────────────────────────────────────────

    @staticmethod
    def _segment_title_for(seg_id: str, topic: str) -> str:
        titles = {
            "intro": f"Welcome to {topic}",
            "content_1": f"Deep Dive: {topic}",
            "guest": f"Expert Interview: {topic}",
            "ad": "Sponsor Break",
            "content_2": f"Key Findings: {topic}",
            "outro": f"Summary & Next Episode on {topic}",
        }
        return titles.get(seg_id, f"Segment: {topic}")

    @staticmethod
    def _segment_prompt_for(seg_id: str, topic: str, category: str) -> str:  # noqa: ARG004 - category reserved for future use
        """Build a dialogue prompt for a segment based on its type and topic."""
        prompts = {
            "intro": (
                f"Welcome the audience to today's show about {topic}. "
                f"Set the stage with enthusiasm and preview what's coming."
            ),
            "content_1": (
                f"Discuss the key developments and latest news about {topic} "
                f"in depth. Cover recent breakthroughs and market impact."
            ),
            "guest": (
                f"Introduce an expert perspective on {topic}. "
                f"Ask insightful questions about the topic's implications."
            ),
            "ad": "Present a sponsor break message naturally. Keep it brief and professional.",
            "content_2": (
                f"Continue the discussion on {topic} with key findings, "
                f"statistics, and future outlook."
            ),
            "outro": (
                f"Wrap up the show about {topic}. Thank the audience "
                f"and tease the next episode."
            ),
        }
        return prompts.get(seg_id, f"Discuss {topic}")

    def _find_matching_persona(
        self, agent_type: AgentType, category: str
    ) -> Optional[PersonaProfile]:
        """Find an existing persona matching agent type and topic category.

        Iterates existing personas and returns the first match by
        agent_type. If no persona exists for the agent type, returns
        None (the host/co-host agents fall back to default templates).
        """
        existing = [
            p for p in self._persona_repo.list() if p.agent_type == agent_type
        ]
        # Return first matching persona if any exist; preferring one whose
        # background_story or name hints at the category (fuzzy match).
        for persona in existing:
            if category.lower() in persona.background_story.lower():
                return persona
        return existing[0] if existing else None

    def _create_topic_poll(self, category: str) -> Optional[object]:
        """Create a poll matching the topic category, or a default poll."""
        from broadcast.audience.models import Poll

        template = POLL_TEMPLATES.get(category, DEFAULT_POLL)
        question, options = template
        try:
            poll = self._polls.create_poll(question, options, duration_seconds=60)
            return poll
        except Exception:
            logger.exception("Failed to create poll for category '%s'", category)
            return None

    def _submit_topic_research(self, topic: str, category: str) -> list[str]:
        """Submit research queries for the topic and return result IDs."""
        ids: list[str] = []

        # Main content research
        try:
            result = self._research.submit_research(
                query=f"{topic} latest developments and analysis",
                segment_id="content_1",
                segment_title=f"Deep Dive: {topic}",
                context=f"Category: {category}",
            )
            if result and "id" in result:
                ids.append(result["id"])
        except Exception:
            logger.exception("Research submission failed for content_1")

        # Guest segment research
        try:
            guest_result = self._research.submit_research(
                query=f"{topic} expert perspectives and interviews",
                segment_id="guest",
                segment_title=f"Expert Interview: {topic}",
                context=f"Category: {category}",
            )
            if guest_result and "id" in guest_result:
                ids.append(guest_result["id"])
        except Exception:
            logger.exception("Research submission failed for guest")

        # Follow-up content research
        try:
            followup_result = self._research.submit_research(
                query=f"{topic} statistics data and future projections",
                segment_id="content_2",
                segment_title=f"Key Findings: {topic}",
                context=f"Category: {category}",
            )
            if followup_result and "id" in followup_result:
                ids.append(followup_result["id"])
        except Exception:
            logger.exception("Research submission failed for content_2")

        return ids

    def _generate_show_assets(self, category: str, topic: str) -> int:
        """Generate media assets (chart, overlays) for the show. Returns count."""
        count = 0

        # Category chart
        try:
            chart_asset = self._generate_topic_chart(category)
            if chart_asset:
                self._media.assign_to_segment(chart_asset.id, "content_1")
                self._asset_ids.append(chart_asset.id)
                count += 1
        except Exception:
            logger.exception("Chart generation failed")

        # Intro text overlay
        try:
            intro = self._media.generate_text_overlay(
                TextOverlayConfig(
                    text=topic,
                    font_size=48,
                    color="#FFFFFF",
                    background_color="#1E3A5F",
                    width=800,
                    height=200,
                )
            )
            self._media.assign_to_segment(intro.id, "intro")
            self._asset_ids.append(intro.id)
            count += 1
        except Exception:
            logger.exception("Intro overlay generation failed")

        # Sponsor overlay
        try:
            sponsor = self._media.generate_text_overlay(
                TextOverlayConfig(
                    text="Sponsored Segment",
                    font_size=36,
                    color="#FFD700",
                    background_color="#333333",
                    width=800,
                    height=150,
                )
            )
            self._media.assign_to_segment(sponsor.id, "ad")
            self._asset_ids.append(sponsor.id)
            count += 1
        except Exception:
            logger.exception("Sponsor overlay generation failed")

        # Outro overlay
        try:
            outro = self._media.generate_text_overlay(
                TextOverlayConfig(
                    text="Thanks for watching! See you next time.",
                    font_size=40,
                    color="#FFFFFF",
                    background_color="#1E3A5F",
                    width=800,
                    height=200,
                )
            )
            self._media.assign_to_segment(outro.id, "outro")
            self._asset_ids.append(outro.id)
            count += 1
        except Exception:
            logger.exception("Outro overlay generation failed")

        return count

    def _generate_topic_chart(self, category: str) -> Optional[object]:
        """Generate a chart asset based on the topic category template."""
        template = TOPIC_CHART_TEMPLATES.get(category)
        if template is None:
            return None

        config = ChartConfig(
            chart_type=template["chart_type"],
            title=template["title"],
            labels=list(template["labels"]),
            datasets=list(template["datasets"]),
        )
        return self._media.generate_chart(config)

    async def _try_obs_connect(self) -> bool:
        """Attempt to connect to OBS. Returns True on success."""
        if not self._obs:
            return False
        try:
            await self._obs.connect()
            logger.info("OBS connected for show run")
            return True
        except Exception:
            logger.warning("OBS not available — running without scene switching")
            return False

    async def _try_obs_scene_switch(self, scene_name: str) -> bool:
        """Attempt to switch to a named OBS scene. Returns True on success."""
        if not self._obs:
            return False
        try:
            await self._obs.switch_scene(scene_name)
            logger.info("OBS scene switched to '%s'", scene_name)
            return True
        except Exception:
            logger.warning("Failed to switch OBS scene to '%s'", scene_name)
            return False

    def _publish_event(self, event_type: str, **extra) -> None:
        """Publish a show event to the EventBus.

        Handles both async contexts (running event loop) and sync
        contexts (e.g. thread pool with no event loop).
        """
        payload = {
            "type": event_type,
            "timestamp": time(),
            **extra,
        }
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            asyncio.run(self._event_bus.publish("broadcast", payload))
        else:
            loop.create_task(self._event_bus.publish("broadcast", payload))

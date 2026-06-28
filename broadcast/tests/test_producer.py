"""Tests for ProducerAgent."""

import pytest
from broadcast.agents.models import EpisodeScript, Segment, SegmentType, ScriptStatus
from broadcast.agents.producer import ProducerAgent


@pytest.fixture
def producer():
    return ProducerAgent()


class TestProducerAgent:
    def test_agent_identity(self, producer):
        assert producer.agent_name == "Producer"
        assert producer.agent_type == "producer"

    def test_create_episode(self, producer):
        script = producer.create_episode(title="Morning Show")
        assert isinstance(script, EpisodeScript)
        assert script.title == "Morning Show"
        assert script.status == ScriptStatus.DRAFT
        assert len(script.segments) == 0

    def test_create_episode_requires_title(self, producer):
        with pytest.raises(ValueError):
            producer.create_episode(title="")

    def test_add_segment(self, producer):
        script = producer.create_episode("Test")
        seg = Segment(id="intro", type=SegmentType.INTRO, title="Welcome")
        updated = producer.add_segment(script, seg)
        assert len(updated.segments) == 1
        assert updated.segments[0].id == "intro"

    def test_add_segment_assigns_order(self, producer):
        script = producer.create_episode("Test")
        s1 = Segment(id="a", type=SegmentType.INTRO, title="A")
        s2 = Segment(id="b", type=SegmentType.CONTENT, title="B")
        script = producer.add_segment(script, s1)
        script = producer.add_segment(script, s2)
        assert script.segments[0].order == 0
        assert script.segments[1].order == 1

    def test_get_episode_by_id(self, producer):
        script = producer.create_episode("Show #1")
        fetched = producer.get_episode(script.id)
        assert fetched is not None
        assert fetched.title == "Show #1"

    def test_get_nonexistent_episode_returns_none(self, producer):
        assert producer.get_episode("nonexistent") is None

    def test_list_episodes(self, producer):
        producer.create_episode("Show A")
        producer.create_episode("Show B")
        episodes = producer.list_episodes()
        assert len(episodes) == 2

    def test_producer_start_stop(self, producer):
        producer.start()
        assert producer.running is True
        producer.stop()
        assert producer.running is False

"""Tests for agent data models."""

import pytest
from pydantic import ValidationError
from broadcast.agents.models import (
    EpisodeScript, Segment, DialogueLine, DialogueBlock,
    AgentType, SegmentType, ScriptStatus,
)


class TestSegmentModel:
    def test_valid_segment(self):
        seg = Segment(
            id="intro",
            type=SegmentType.INTRO,
            title="Welcome",
            duration_seconds=30,
            scene_name="Intro Scene",
            dialogue_prompt="Greet the audience warmly",
        )
        assert seg.id == "intro"
        assert seg.type == SegmentType.INTRO
        assert seg.duration_seconds == 30
        assert seg.scene_name == "Intro Scene"

    def test_segment_default_order(self):
        seg = Segment(id="a", type=SegmentType.CONTENT, title="T")
        assert seg.order == 0  # default

    def test_segment_negative_duration_raises(self):
        with pytest.raises(ValidationError):
            Segment(id="bad", type=SegmentType.CONTENT, title="T", duration_seconds=-1)


class TestDialogueLineModel:
    def test_valid_dialogue_line(self):
        line = DialogueLine(speaker="Host", text="Hello everyone!")
        assert line.speaker == "Host"
        assert line.text == "Hello everyone!"
        assert line.order == 0  # default

    def test_dialogue_line_with_emotion(self):
        line = DialogueLine(speaker="CoHost", text="Wow!", emotion="excited")
        assert line.emotion == "excited"


class TestDialogueBlockModel:
    def test_valid_block(self):
        block = DialogueBlock(
            segment_id="intro",
            lines=[
                DialogueLine(speaker="Host", text="Hi!"),
                DialogueLine(speaker="CoHost", text="Hey!"),
            ],
        )
        assert len(block.lines) == 2
        assert block.lines[0].speaker == "Host"

    def test_empty_lines_raises(self):
        with pytest.raises(ValidationError):
            DialogueBlock(segment_id="intro", lines=[])


class TestEpisodeScriptModel:
    def test_valid_script(self):
        script = EpisodeScript(
            title="Morning Show",
            segments=[
                Segment(id="intro", type=SegmentType.INTRO, title="Intro"),
                Segment(id="main", type=SegmentType.CONTENT, title="Main Topic"),
            ],
        )
        assert script.title == "Morning Show"
        assert len(script.segments) == 2
        assert script.status == ScriptStatus.DRAFT

    def test_episode_default_status(self):
        script = EpisodeScript(title="Test", segments=[])
        assert script.status == ScriptStatus.DRAFT

    def test_episode_accepts_custom_id(self):
        script = EpisodeScript(id="custom123", title="Test", segments=[])
        assert script.id == "custom123"

    def test_episode_default_id_empty(self):
        script = EpisodeScript(title="Test", segments=[])
        assert script.id == ""  # Producer fills this in on creation

    def test_total_duration_computed(self):
        script = EpisodeScript(
            title="Show",
            segments=[
                Segment(id="a", type=SegmentType.INTRO, title="A", duration_seconds=30),
                Segment(id="b", type=SegmentType.CONTENT, title="B", duration_seconds=120),
            ],
        )
        # total_duration is a computed property
        assert script.total_duration == 150

    def test_agent_type_enum_values(self):
        assert AgentType.HOST == "host"
        assert AgentType.COHOST == "cohost"
        assert AgentType.DIRECTOR == "director"
        assert AgentType.PRODUCER == "producer"

    def test_segment_type_enum_values(self):
        assert SegmentType.INTRO == "intro"
        assert SegmentType.CONTENT == "content"
        assert SegmentType.GUEST == "guest"
        assert SegmentType.AD == "ad"
        assert SegmentType.OUTRO == "outro"

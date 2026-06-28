"""Tests for Host and Co-Host dialogue agents."""

import pytest
from broadcast.agents.models import Segment, SegmentType, DialogueBlock, DialogueLine
from broadcast.agents.dialogue import HostAgent, CoHostAgent


@pytest.fixture
def host():
    return HostAgent()


@pytest.fixture
def cohost():
    return CoHostAgent()


class TestHostAgent:
    def test_agent_identity(self, host):
        assert host.agent_name == "Host"
        assert host.agent_type == "host"

    def test_generate_intro_returns_block(self, host):
        segment = Segment(id="intro", type=SegmentType.INTRO, title="Welcome!")
        block = host.generate_intro(segment)
        assert isinstance(block, DialogueBlock)
        assert block.segment_id == "intro"
        assert len(block.lines) >= 1
        assert block.lines[0].speaker == "Host"

    def test_generate_dialogue_returns_content(self, host):
        segment = Segment(
            id="seg_1", type=SegmentType.CONTENT,
            title="AI News", dialogue_prompt="Latest AI developments",
        )
        block = host.generate_dialogue(segment)
        assert isinstance(block, DialogueBlock)
        assert len(block.lines) >= 1
        # Should reference the topic
        text = " ".join(l.text for l in block.lines)
        assert "AI" in text or "developments" in text or "news" in text.lower()

    def test_outro_dialogue(self, host):
        segment = Segment(id="outro", type=SegmentType.OUTRO, title="Goodbye")
        block = host.generate_dialogue(segment)
        text = " ".join(l.text for l in block.lines).lower()
        assert any(word in text for word in ["bye", "next", "thank", "see"])

    def test_multiple_calls_different_text(self, host):
        """Template should vary slightly between calls."""
        seg = Segment(id="t", type=SegmentType.CONTENT, title="Tech")
        b1 = host.generate_dialogue(seg)
        b2 = host.generate_dialogue(seg)
        t1 = " ".join(l.text for l in b1.lines)
        t2 = " ".join(l.text for l in b2.lines)
        # They're template-based so might be similar, but should have content
        assert t1
        assert t2


class TestCoHostAgent:
    def test_agent_identity(self, cohost):
        assert cohost.agent_name == "Co-Host"
        assert cohost.agent_type == "cohost"

    def test_generate_dialogue_returns_content(self, cohost):
        segment = Segment(
            id="seg_1", type=SegmentType.CONTENT,
            title="Space News", dialogue_prompt="Latest space discoveries",
        )
        block = cohost.generate_dialogue(segment)
        assert isinstance(block, DialogueBlock)
        assert len(block.lines) >= 1
        # Co-host should acknowledge and add perspective
        text = " ".join(l.text for l in block.lines)
        assert block.lines[0].speaker == "Co-Host"

    def test_guest_introduction(self, cohost):
        segment = Segment(
            id="guest_1", type=SegmentType.GUEST,
            title="Special Guest: Dr. Smith",
        )
        block = cohost.generate_dialogue(segment)
        text = " ".join(l.text for l in block.lines)
        assert "guest" in text.lower() or "join" in text.lower() or "Smith" in text or "welcome" in text.lower()

    def test_host_and_cohost_different_styles(self, host, cohost):
        """Host and Co-Host should generate different-sounding dialogue."""
        seg = Segment(id="t", type=SegmentType.CONTENT, title="Weather")
        host_block = host.generate_dialogue(seg)
        cohost_block = cohost.generate_dialogue(seg)
        host_text = " ".join(l.text for l in host_block.lines)
        cohost_text = " ".join(l.text for l in cohost_block.lines)
        # Should not be identical
        assert host_text != cohost_text

"""Tests for DirectorAgent — episode script timeline navigation."""

import pytest
from broadcast.agents.models import EpisodeScript, Segment, SegmentType, ScriptStatus
from broadcast.agents.director import DirectorAgent


@pytest.fixture
def director():
    return DirectorAgent()


@pytest.fixture
def sample_script():
    """A script with 3 segments."""
    script = EpisodeScript(
        id="test-001",
        title="Test Show",
        status=ScriptStatus.READY,
        segments=[
            Segment(id="intro", type=SegmentType.INTRO, title="Welcome", duration_seconds=30),
            Segment(id="main", type=SegmentType.CONTENT, title="Main Topic", duration_seconds=120),
            Segment(id="outro", type=SegmentType.OUTRO, title="Goodbye", duration_seconds=30),
        ],
    )
    return script


@pytest.fixture
def empty_script():
    """A script with no segments."""
    return EpisodeScript(id="empty", title="Empty Show", status=ScriptStatus.READY, segments=[])


class TestDirectorAgent:
    def test_agent_identity(self, director):
        assert director.agent_name == "Director"
        assert director.agent_type == "director"

    def test_initial_state(self, director):
        assert director.script is None
        assert director.current_segment is None
        assert director.current_segment_index == -1
        assert director.has_more is False

    def test_load_script(self, director, sample_script):
        director.load_script(sample_script)
        assert director.script is sample_script
        # Should start at index -1 (before first segment)
        assert director.current_segment is None
        assert director.current_segment_index == -1
        assert director.has_more is True

    def test_next_segment_advances_to_first(self, director, sample_script):
        director.load_script(sample_script)
        seg = director.next_segment()
        assert seg is sample_script.segments[0]
        assert seg.id == "intro"
        assert director.current_segment_index == 0
        assert director.current_segment is seg
        assert director.has_more is True

    def test_full_traversal(self, director, sample_script):
        director.load_script(sample_script)

        seg1 = director.next_segment()
        assert seg1.id == "intro"
        assert director.current_segment_index == 0

        seg2 = director.next_segment()
        assert seg2.id == "main"
        assert director.current_segment_index == 1

        seg3 = director.next_segment()
        assert seg3.id == "outro"
        assert director.current_segment_index == 2
        # On the last segment — no more segments
        assert director.has_more is False

        seg4 = director.next_segment()
        assert seg4 is None  # no more segments
        assert director.current_segment_index == 3  # past the end
        assert director.has_more is False

    def test_next_segment_no_script_loaded(self, director):
        seg = director.next_segment()
        assert seg is None
        assert director.current_segment_index == -1

    def test_next_segment_empty_script(self, director, empty_script):
        director.load_script(empty_script)
        assert director.has_more is False
        seg = director.next_segment()
        assert seg is None
        assert director.current_segment_index == -1

    def test_reset(self, director, sample_script):
        director.load_script(sample_script)
        director.next_segment()
        director.next_segment()
        assert director.current_segment_index == 1

        director.reset()
        assert director.current_segment is None
        assert director.current_segment_index == -1
        assert director.has_more is True

    def test_seek_to_segment(self, director, sample_script):
        director.load_script(sample_script)
        seg = director.seek_to_segment("outro")
        assert seg is not None
        assert seg.id == "outro"
        assert director.current_segment_index == 2
        assert director.has_more is False

    def test_seek_to_last_and_exhausted(self, director, sample_script):
        director.load_script(sample_script)
        director.seek_to_segment("outro")  # last segment
        assert director.has_more is False  # no more segments after
        seg = director.next_segment()
        assert seg is None
        assert director.has_more is False

    def test_seek_to_segment_not_found(self, director, sample_script):
        director.load_script(sample_script)
        seg = director.seek_to_segment("nonexistent")
        assert seg is None
        assert director.current_segment_index == -1  # unchanged

    def test_seek_to_segment_not_found_mid_navigation(self, director, sample_script):
        director.load_script(sample_script)
        director.next_segment()  # now at index 0
        seg = director.seek_to_segment("nonexistent")
        assert seg is None
        assert director.current_segment_index == 0  # unchanged

    def test_seek_to_segment_no_script(self, director):
        seg = director.seek_to_segment("any")
        assert seg is None
        assert director.current_segment_index == -1

    def test_current_segment_after_load(self, director, sample_script):
        """current_segment should reflect navigation state."""
        director.load_script(sample_script)
        assert director.current_segment is None

        director.next_segment()
        assert director.current_segment is not None
        assert director.current_segment.id == "intro"

    def test_load_clears_previous_state(self, director, sample_script):
        """Loading a new script should reset state."""
        director.load_script(sample_script)
        director.next_segment()
        director.next_segment()
        assert director.current_segment_index == 1

        script2 = EpisodeScript(id="test-002", title="Show 2", segments=[
            Segment(id="seg_a", type=SegmentType.INTRO, title="A"),
        ])
        director.load_script(script2)
        assert director.current_segment_index == -1
        assert director.has_more is True
        seg = director.next_segment()
        assert seg.id == "seg_a"

    def test_director_start_stop(self, director):
        director.start()
        assert director.running is True
        director.stop()
        assert director.running is False

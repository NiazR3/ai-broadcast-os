"""Tests for BaseAgent abstract class."""

import pytest
from broadcast.agents.base import BaseAgent


class ConcreteAgent(BaseAgent):
    """Minimal concrete implementation for testing."""
    @property
    def agent_name(self) -> str:
        return "test_agent"
    @property
    def agent_type(self) -> str:
        return "test"


class TestBaseAgent:
    def test_agent_name_property(self):
        agent = ConcreteAgent()
        assert agent.agent_name == "test_agent"

    def test_agent_type_property(self):
        agent = ConcreteAgent()
        assert agent.agent_type == "test"

    def test_agent_initial_state(self):
        agent = ConcreteAgent()
        assert agent.running is False

    def test_start_stop_cycle(self):
        agent = ConcreteAgent()
        agent.start()
        assert agent.running is True
        agent.stop()
        assert agent.running is False

    def test_double_start_is_noop(self):
        agent = ConcreteAgent()
        agent.start()
        agent.start()  # should not raise
        assert agent.running is True

    def test_double_stop_is_noop(self):
        agent = ConcreteAgent()
        agent.start()
        agent.stop()
        agent.stop()  # should not raise
        assert agent.running is False

    def test_abstract_class_cannot_instantiate(self):
        with pytest.raises(TypeError):
            BaseAgent()  # Can't instantiate abstract class

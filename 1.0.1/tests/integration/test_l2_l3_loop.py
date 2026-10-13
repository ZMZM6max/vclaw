"""Integration test: L2 calls L3 and orchestrates the ReAct loop."""
import pytest

pytestmark = pytest.mark.contract

import sys
sys.path.insert(0, 'src')
from unittest.mock import Mock, MagicMock
from src.core.models import StandardEvent, SessionContext, AgentAction, Observation, L3Input
from src.l2.l2_control_gateway import ControlGateway
from src.core.exceptions import MaxIterationsExceeded


class MockL3Orchestrator:
    """Mock L3 that returns AgentAction on first call, str on second."""

    def __init__(self):
        self.call_count = 0

    def run(self, context: SessionContext, observation=None):
        self.call_count += 1
        if self.call_count == 1:
            return AgentAction(action="calculator", action_input={"expression": "2+2"})
        return "The answer is 4."


class MockTools:
    """Mock L5 tools."""

    def execute(self, action_name, params, timeout=30):
        return Observation(status="success", result="4", execution_time=0.1)

    def get_available_tools(self, user_permissions=None):
        return []

    def list_tools(self):
        return []


class TestL2L3Loop:
    """Test that L2 correctly orchestrates the L3->L5->L3 loop."""

    def test_l2_calls_l3_and_returns_final_response(self):
        mock_l3 = MockL3Orchestrator()
        mock_tools = MockTools()
        mock_memory = Mock()
        mock_memory.retrieve_history.return_value = []
        mock_memory.search.return_value = []
        mock_memory.store_conversation.return_value = True

        gateway = ControlGateway(
            memory=mock_memory,
            tools=mock_tools,
            l3_orchestrator=mock_l3
        )

        event = StandardEvent(
            channel="test",
            user_id="user_123",
            content="What is 2+2?"
        )

        result = gateway.process_event(event)

        assert result == "The answer is 4."
        assert mock_l3.call_count == 2

    def test_l2_returns_direct_answer_without_tools(self):
        mock_l3 = Mock()
        mock_l3.run.return_value = "Hello! How can I help?"
        mock_tools = MockTools()
        mock_memory = Mock()
        mock_memory.retrieve_history.return_value = []
        mock_memory.search.return_value = []

        gateway = ControlGateway(
            memory=mock_memory,
            tools=mock_tools,
            l3_orchestrator=mock_l3
        )

        event = StandardEvent(channel="test", user_id="user_123", content="Hi")
        result = gateway.process_event(event)

        assert result == "Hello! How can I help?"
        mock_l3.run.assert_called_once()

    def test_l2_respects_max_iterations(self):
        """If L3 keeps returning AgentAction, L2 should stop after max iterations."""

        class AlwaysActionL3:
            def run(self, context, observation=None):
                return AgentAction(action="calculator", action_input={"expression": "1+1"})

        mock_l3 = AlwaysActionL3()
        mock_tools = MockTools()
        mock_memory = Mock()
        mock_memory.retrieve_history.return_value = []
        mock_memory.search.return_value = []

        gateway = ControlGateway(
            memory=mock_memory,
            tools=mock_tools,
            l3_orchestrator=mock_l3
        )

        event = StandardEvent(channel="test", user_id="user_123", content="loop forever")

        with pytest.raises(MaxIterationsExceeded):
            gateway.process_event(event)

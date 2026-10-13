"""Tests for L2-L3 contract.

Verifies the interface contract between L2 ControlGateway and L3 Orchestration.
"""
import pytest

pytestmark = pytest.mark.contract
from unittest.mock import Mock, patch
import sys
sys.path.insert(0, 'src')

from src.l2.l2_control_gateway import ControlGateway
from src.core.models import StandardEvent, L3Input, SessionContext


class TestL2L3Contract:
    """Tests for L2-L3 interface contract."""

    def test_l2_outputs_l3input_type(self):
        """Verify L2 process_event outputs L3Input type."""
        gateway = ControlGateway()
        event = StandardEvent(
            channel="test",
            user_id="user_123",
            content="Hello",
            metadata={}
        )

        with patch.object(gateway.memory, 'retrieve_history', return_value=[]), \
             patch.object(gateway.memory_accessor, 'retrieve_relevant', return_value=[]), \
             patch.object(gateway.tool_preparer, 'prepare_tools', return_value=[]):

            result = gateway.process_event(event)

            assert isinstance(result, L3Input), "L2 must output L3Input type"

    def test_l3input_contains_session_context(self):
        """Verify L3Input contains valid SessionContext."""
        gateway = ControlGateway()
        event = StandardEvent(
            channel="websocket",
            user_id="user_456",
            content="Test query",
            metadata={}
        )

        with patch.object(gateway.memory, 'retrieve_history', return_value=[]), \
             patch.object(gateway.memory_accessor, 'retrieve_relevant', return_value=[]), \
             patch.object(gateway.tool_preparer, 'prepare_tools', return_value=[]):

            result = gateway.process_event(event)

            assert isinstance(result.session_context, SessionContext)
            assert result.session_context.user_id == "user_456"
            assert result.session_context.current_query == "Test query"
            assert result.session_context.session_id is not None

    def test_l3input_contains_available_tools(self):
        """Verify L3Input contains available_tools list."""
        gateway = ControlGateway()
        event = StandardEvent(channel="test", user_id="u1", content="Hi", metadata={})

        mock_tools = [{"name": "calc"}, {"name": "search"}]

        with patch.object(gateway.memory, 'retrieve_history', return_value=[]), \
             patch.object(gateway.memory_accessor, 'retrieve_relevant', return_value=[]), \
             patch.object(gateway.tool_preparer, 'prepare_tools', return_value=mock_tools):

            result = gateway.process_event(event)

            assert isinstance(result.available_tools, list)
            assert len(result.available_tools) == 2
            assert result.available_tools[0]["name"] == "calc"

    def test_l3input_contains_relevant_memories(self):
        """Verify L3Input contains relevant_memories list."""
        gateway = ControlGateway()
        event = StandardEvent(channel="test", user_id="u1", content="Hi", metadata={})

        mock_memories = ["Memory 1", "Memory 2"]

        with patch.object(gateway.memory, 'retrieve_history', return_value=[]), \
             patch.object(gateway.memory_accessor, 'retrieve_relevant', return_value=mock_memories), \
             patch.object(gateway.tool_preparer, 'prepare_tools', return_value=[]):

            result = gateway.process_event(event)

            assert isinstance(result.relevant_memories, list)
            assert len(result.relevant_memories) == 2
            assert result.relevant_memories[0] == "Memory 1"

    def test_session_context_has_required_fields(self):
        """Verify SessionContext has all fields required by L3."""
        gateway = ControlGateway()
        event = StandardEvent(
            channel="telegram",
            user_id="user_789",
            content="What's the weather?",
            metadata={}
        )

        with patch.object(gateway.memory, 'retrieve_history', return_value=[{"role": "user", "content": "Hi"}]), \
             patch.object(gateway.memory_accessor, 'retrieve_relevant', return_value=[]), \
             patch.object(gateway.tool_preparer, 'prepare_tools', return_value=[]):

            result = gateway.process_event(event)
            ctx = result.session_context

            # Verify all required fields
            assert hasattr(ctx, 'session_id') and ctx.session_id
            assert hasattr(ctx, 'user_id') and ctx.user_id == "user_789"
            assert hasattr(ctx, 'current_query') and ctx.current_query == "What's the weather?"
            assert hasattr(ctx, 'history') and isinstance(ctx.history, list)
            assert hasattr(ctx, 'user_permissions') and isinstance(ctx.user_permissions, list)
            assert hasattr(ctx, 'metadata')

    def test_l3input_optional_fields_have_defaults(self):
        """Verify L3Input optional fields have appropriate defaults."""
        gateway = ControlGateway()
        event = StandardEvent(channel="test", user_id="u1", content="Hi", metadata={})

        with patch.object(gateway.memory, 'retrieve_history', return_value=[]), \
             patch.object(gateway.memory_accessor, 'retrieve_relevant', return_value=[]), \
             patch.object(gateway.tool_preparer, 'prepare_tools', return_value=[]):

            result = gateway.process_event(event)

            # Optional fields should have default empty lists
            assert result.available_tools == []
            assert result.relevant_memories == []

    def test_tools_have_required_fields(self):
        """Verify tools in available_tools have required fields."""
        gateway = ControlGateway()
        event = StandardEvent(channel="test", user_id="u1", content="Hi", metadata={})

        mock_tools = [
            {"name": "calculator", "description": "Math calc", "parameters": {"expr": {"type": "string"}}}
        ]

        with patch.object(gateway.memory, 'retrieve_history', return_value=[]), \
             patch.object(gateway.memory_accessor, 'retrieve_relevant', return_value=[]), \
             patch.object(gateway.tool_preparer, 'prepare_tools', return_value=mock_tools):

            result = gateway.process_event(event)
            tool = result.available_tools[0]

            # Tools should have name and description at minimum
            assert "name" in tool
            assert "description" in tool

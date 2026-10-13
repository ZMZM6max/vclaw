"""Integration tests for L2 Control Gateway.

Tests the complete flow through L2 components.
"""
import pytest
from unittest.mock import Mock, patch
import sys
sys.path.insert(0, 'src')

from src.l2.l2_control_gateway import (
    ControlGateway, RateLimiter, MemoryAccessor, ToolPreparer,
    RateLimitExceeded
)
from src.core.models import StandardEvent, SessionContext, L3Input


class TestL2Integration:
    """Integration tests for L2 Control Gateway components."""

    def test_complete_flow_with_all_components(self):
        """Test complete flow through all L2 components."""
        # Setup
        gateway = ControlGateway()
        event = StandardEvent(
            channel="telegram",
            user_id="user_123",
            content="What can you do?",
            metadata={"client_ip": "192.168.1.1"}
        )

        # Mock L4 response
        mock_history = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"}
        ]
        mock_memories = [
            "User is interested in AI capabilities",
            "User prefers detailed explanations"
        ]

        with patch.object(gateway.memory, 'retrieve_history', return_value=mock_history), \
             patch.object(gateway.memory_accessor, 'retrieve_relevant', return_value=mock_memories):

            # Execute
            result = gateway.process_event(event)

            # Verify complete L3Input
            assert isinstance(result, L3Input)
            assert result.session_context.user_id == "user_123"
            assert result.session_context.current_query == "What can you do?"
            assert len(result.session_context.history) == 2
            assert len(result.relevant_memories) == 2
            assert isinstance(result.available_tools, list)

    def test_rate_limit_integration(self):
        """Test rate limiting in complete flow."""
        gateway = ControlGateway()

        # Exhaust rate limit
        for i in range(60):
            event = StandardEvent(
                channel="test",
                user_id="rate_limited_user",
                content=f"Message {i}",
                metadata={}
            )
            try:
                with patch.object(gateway.memory, 'retrieve_history', return_value=[]), \
                     patch.object(gateway.memory_accessor, 'retrieve_relevant', return_value=[]), \
                     patch.object(gateway.tool_preparer, 'prepare_tools', return_value=[]):
                    gateway.process_event(event)
            except RateLimitExceeded:
                pass

        # Next request should be blocked
        blocked_event = StandardEvent(
            channel="test",
            user_id="rate_limited_user",
            content="Blocked message",
            metadata={}
        )

        with pytest.raises(RateLimitExceeded):
            with patch.object(gateway.memory, 'retrieve_history', return_value=[]), \
                 patch.object(gateway.memory_accessor, 'retrieve_relevant', return_value=[]), \
                 patch.object(gateway.tool_preparer, 'prepare_tools', return_value=[]):
                gateway.process_event(blocked_event)

    def test_session_persistence_across_requests(self):
        """Test session is persisted across multiple requests."""
        gateway = ControlGateway()
        user_id = "persistent_user"

        # First request - create session
        event1 = StandardEvent(
            channel="websocket",
            user_id=user_id,
            content="First message",
            metadata={}
        )

        with patch.object(gateway.memory, 'retrieve_history', return_value=[]), \
             patch.object(gateway.memory_accessor, 'retrieve_relevant', return_value=[]), \
             patch.object(gateway.tool_preparer, 'prepare_tools', return_value=[]):
            result1 = gateway.process_event(event1)
            session_id_1 = result1.session_context.session_id

        # Second request with same user - should reuse session
        event2 = StandardEvent(
            channel="websocket",
            user_id=user_id,
            content="Second message",
            metadata={"session_id": session_id_1}
        )

        with patch.object(gateway.memory, 'retrieve_history', return_value=[]), \
             patch.object(gateway.memory_accessor, 'retrieve_relevant', return_value=[]), \
             patch.object(gateway.tool_preparer, 'prepare_tools', return_value=[]):
            result2 = gateway.process_event(event2)
            session_id_2 = result2.session_context.session_id

        # Same session should be used
        assert session_id_1 == session_id_2

    def test_different_users_get_different_sessions(self):
        """Test different users get different sessions."""
        gateway = ControlGateway()

        event1 = StandardEvent(channel="test", user_id="user_a", content="Hi", metadata={})
        event2 = StandardEvent(channel="test", user_id="user_b", content="Hi", metadata={})

        with patch.object(gateway.memory, 'retrieve_history', return_value=[]), \
             patch.object(gateway.memory_accessor, 'retrieve_relevant', return_value=[]), \
             patch.object(gateway.tool_preparer, 'prepare_tools', return_value=[]):
            result1 = gateway.process_event(event1)
            result2 = gateway.process_event(event2)

        assert result1.session_context.session_id != result2.session_context.session_id

    def test_memory_accessor_filters_by_user(self):
        """Test MemoryAccessor filters memories by user_id."""
        from src.core.models import Document

        mock_memory = Mock()
        mock_memory.search.return_value = [
            Document(id="1", content="User A's preference", metadata={})
        ]

        accessor = MemoryAccessor(memory=mock_memory)
        memories = accessor.retrieve_relevant(
            query="test",
            user_id="user_a",
            top_k=5
        )

        # Verify search was called with user filter
        call_args = mock_memory.search.call_args
        assert call_args.kwargs['filters']['user_id'] == "user_a"

    def test_tool_preparer_respects_permissions(self):
        """Test ToolPreparer correctly filters by permissions."""
        mock_tools = Mock()
        mock_tools.list_tools.return_value = [
            {"name": "calculator", "description": "Math"},
            {"name": "file_read", "description": "Read"},
            {"name": "terminal", "description": "Terminal"}
        ]

        preparer = ToolPreparer(tools=mock_tools)

        # No permissions - only calculator
        available_no_perms = preparer.prepare_tools([])
        assert len(available_no_perms) == 1
        assert available_no_perms[0]["name"] == "calculator"

        # With file_read permission
        available_with_perms = preparer.prepare_tools(["file_read"])
        tool_names = [t["name"] for t in available_with_perms]
        assert "calculator" in tool_names
        assert "file_read" in tool_names

    def test_new_session_with_ip_tracking(self):
        """Test new session creation with IP tracking for rate limiting."""
        gateway = ControlGateway()

        event = StandardEvent(
            channel="webhook",
            user_id="new_user",
            content="Hello",
            metadata={"client_ip": "10.0.0.5"}
        )

        with patch.object(gateway.rate_limiter, 'is_allowed') as mock_limiter, \
             patch.object(gateway.memory, 'retrieve_history', return_value=[]), \
             patch.object(gateway.memory_accessor, 'retrieve_relevant', return_value=[]), \
             patch.object(gateway.tool_preparer, 'prepare_tools', return_value=[]):

            mock_limiter.return_value = (True, None)
            result = gateway.process_event(event)

            # Verify IP was passed to rate limiter
            mock_limiter.assert_called_once_with(user_id="new_user", ip="10.0.0.5")
            assert result.session_context.session_id is not None


class TestL2ErrorHandling:
    """Tests for L2 error handling scenarios."""

    def test_rate_limit_error_message(self):
        """Test rate limit error includes reason."""
        gateway = ControlGateway()
        limiter = gateway.rate_limiter

        # Exhaust user limit
        for _ in range(60):
            limiter.is_allowed("test_user")

        # Next request should be blocked
        allowed, reason = limiter.is_allowed("test_user")
        assert allowed is False
        assert reason == "user_rate_limit"

    def test_memory_search_failure_handling(self):
        """Test graceful handling of L4 memory search failure."""
        gateway = ControlGateway()
        event = StandardEvent(channel="test", user_id="u1", content="Hi", metadata={})

        # Mock memory to raise exception — L2 should degrade to empty list
        with patch.object(gateway.memory, 'retrieve_history', return_value=[]), \
             patch.object(gateway.memory_accessor, 'retrieve_relevant', side_effect=Exception("L4 Error")), \
             patch.object(gateway.tool_preparer, 'prepare_tools', return_value=[]):

            result = gateway.process_event(event)

            # Should return valid L3Input with empty memories due to graceful degradation
            assert isinstance(result, L3Input)
            assert result.relevant_memories == []

    def test_empty_tool_list_handling(self):
        """Test handling when no tools are available."""
        gateway = ControlGateway()
        event = StandardEvent(channel="test", user_id="u1", content="Hi", metadata={})

        with patch.object(gateway.memory, 'retrieve_history', return_value=[]), \
             patch.object(gateway.memory_accessor, 'retrieve_relevant', return_value=[]), \
             patch.object(gateway.tool_preparer, 'prepare_tools', return_value=[]):

            result = gateway.process_event(event)

            # Should still return valid L3Input with empty tools list
            assert isinstance(result, L3Input)
            assert result.available_tools == []

"""Tests for ControlGateway component.

TC-L2-001: Session creation and context assembly
TC-L2-002: Rate limit triggered
TC-L2-004: History retrieval and concatenation
TC-L2-006: Send response
TC-L2-NOAUTH: No authentication required
TC-ControlGateway-007: process_event returns L3Input
TC-ControlGateway-008: Passes IP to rate limiter
"""
import pytest
from unittest.mock import Mock, patch
import sys
sys.path.insert(0, 'src')

from src.l2.l2_control_gateway import ControlGateway, RateLimitExceeded, ToolPreparer
from src.core.models import StandardEvent, SessionContext, L3Input


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def control_gateway():
    """Provide ControlGateway instance."""
    return ControlGateway()


@pytest.fixture
def sample_event():
    """Provide sample StandardEvent."""
    return StandardEvent(
        channel="test",
        user_id="user_123",
        content="Hello",
        metadata={}
    )


@pytest.fixture
def sample_event_with_session():
    """Provide StandardEvent with existing session."""
    return StandardEvent(
        channel="test",
        user_id="user_123",
        content="What's the weather?",
        metadata={"session_id": "existing_session_123"}
    )


# =============================================================================
# Basic ControlGateway Tests
# =============================================================================

class TestControlGateway:
    """Tests for L2 Control Gateway."""

    def test_session_creation_and_context_assembly(self, control_gateway, sample_event):
        """TC-L2-001: 会话创建与上下文组装."""
        # Mock dependencies
        with patch.object(control_gateway.memory, 'retrieve_history', return_value=[]), \
             patch.object(control_gateway.memory_accessor, 'retrieve_relevant', return_value=[]), \
             patch.object(control_gateway.tool_preparer, 'prepare_tools', return_value=[]):

            # Execute
            l3_input = control_gateway.process_event(sample_event)

            # Verify - now returns L3Input
            assert l3_input.session_context.user_id == "user_123"
            assert l3_input.session_context.current_query == "Hello"
            assert l3_input.session_context.session_id is not None

    def test_rate_limit_triggered(self, control_gateway):
        """TC-L2-002: 限流触发."""
        # Mock dependencies for all calls
        def mock_process():
            with patch.object(control_gateway.memory, 'retrieve_history', return_value=[]), \
                 patch.object(control_gateway.memory_accessor, 'retrieve_relevant', return_value=[]), \
                 patch.object(control_gateway.tool_preparer, 'prepare_tools', return_value=[]):
                event = StandardEvent(
                    channel="test",
                    user_id="user_123",
                    content="Test",
                    metadata={}
                )
                return control_gateway.process_event(event)

        # First 60 requests should succeed
        for i in range(60):
            try:
                mock_process()
            except RateLimitExceeded:
                pass  # Might happen near the limit

        # 61st request should fail
        with pytest.raises(RateLimitExceeded):
            mock_process()

    def test_history_retrieval_and_concatenation(self, control_gateway, sample_event_with_session):
        """TC-L2-004: 历史记录检索与拼接."""
        # Mock history retrieval
        mock_history = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi!"}
        ]

        with patch.object(control_gateway.memory, 'retrieve_history', return_value=mock_history), \
             patch.object(control_gateway.memory_accessor, 'retrieve_relevant', return_value=[]), \
             patch.object(control_gateway.tool_preparer, 'prepare_tools', return_value=[]):

            # Execute
            l3_input = control_gateway.process_event(sample_event_with_session)

            # Verify
            assert len(l3_input.session_context.history) == 2
            assert l3_input.session_context.history[0]["content"] == "Hello"
            assert l3_input.session_context.current_query == "What's the weather?"

    def test_send_response(self, control_gateway):
        """TC-L2-006: 响应发送."""
        event = StandardEvent(
            channel="test",
            user_id="user_123",
            content="Hello",
            metadata={"session_id": "test_session_123"}
        )

        # Execute
        result = control_gateway.send_response(event, "Hello user")

        # Verify
        assert result is True

    def test_no_auth_required(self, control_gateway, sample_event):
        """TC-L2-NOAUTH: 身份认证已移除，无需令牌."""
        # Mock dependencies
        with patch.object(control_gateway.memory, 'retrieve_history', return_value=[]), \
             patch.object(control_gateway.memory_accessor, 'retrieve_relevant', return_value=[]), \
             patch.object(control_gateway.tool_preparer, 'prepare_tools', return_value=[]):

            # Execute - should succeed without auth
            l3_input = control_gateway.process_event(sample_event)

            # Verify
            assert l3_input.session_context.user_id == "user_123"
            # MVP阶段：所有用户默认拥有全部权限
            assert l3_input.session_context.user_permissions == ToolPreparer.ALL_PERMISSIONS


# =============================================================================
# Enhanced ControlGateway Tests
# =============================================================================

class TestControlGatewayEnhanced:
    """Tests for enhanced ControlGateway that outputs L3Input."""

    def test_process_event_returns_l3input(self, control_gateway, sample_event):
        """TC-ControlGateway-007: process_event returns L3Input."""
        # Mock dependencies
        with patch.object(control_gateway.memory, 'retrieve_history', return_value=[]), \
             patch.object(control_gateway.memory_accessor, 'retrieve_relevant', return_value=["Memory 1"]), \
             patch.object(control_gateway.tool_preparer, 'prepare_tools', return_value=[{"name": "calc"}]):

            result = control_gateway.process_event(sample_event)

            # Should return L3Input
            assert isinstance(result, L3Input)
            assert result.session_context.user_id == "user_123"
            assert len(result.available_tools) == 1
            assert len(result.relevant_memories) == 1

    def test_process_event_passes_ip_to_rate_limiter(self, control_gateway):
        """TC-ControlGateway-008: Passes IP from metadata to rate limiter."""
        event = StandardEvent(
            channel="test",
            user_id="user_123",
            content="Hello",
            metadata={"client_ip": "192.168.1.1"}
        )

        with patch.object(control_gateway.memory, 'retrieve_history', return_value=[]), \
             patch.object(control_gateway.rate_limiter, 'is_allowed') as mock_limiter, \
             patch.object(control_gateway.memory_accessor, 'retrieve_relevant', return_value=[]), \
             patch.object(control_gateway.tool_preparer, 'prepare_tools', return_value=[]):

            mock_limiter.return_value = (True, None)
            control_gateway.process_event(event)

            # Verify IP was passed
            mock_limiter.assert_called_once_with(user_id="user_123", ip="192.168.1.1")

    def test_process_event_includes_all_l3input_fields(self, control_gateway, sample_event):
        """Verify L3Input contains all required fields."""
        mock_history = [{"role": "user", "content": "Previous message"}]
        mock_memories = ["User preference 1", "User preference 2"]
        mock_tools = [{"name": "tool1"}, {"name": "tool2"}]

        with patch.object(control_gateway.memory, 'retrieve_history', return_value=mock_history), \
             patch.object(control_gateway.memory_accessor, 'retrieve_relevant', return_value=mock_memories), \
             patch.object(control_gateway.tool_preparer, 'prepare_tools', return_value=mock_tools):

            result = control_gateway.process_event(sample_event)

            # Verify all L3Input fields
            assert isinstance(result, L3Input)
            assert result.session_context is not None
            assert result.session_context.user_id == "user_123"
            assert result.session_context.current_query == "Hello"
            assert len(result.session_context.history) == 1
            assert len(result.relevant_memories) == 2
            assert len(result.available_tools) == 2

    def test_session_context_contains_metadata(self, control_gateway, sample_event):
        """Verify session context includes channel and event metadata."""
        sample_event.metadata = {"custom_field": "custom_value", "client_ip": "1.2.3.4"}

        with patch.object(control_gateway.memory, 'retrieve_history', return_value=[]), \
             patch.object(control_gateway.memory_accessor, 'retrieve_relevant', return_value=[]), \
             patch.object(control_gateway.tool_preparer, 'prepare_tools', return_value=[]):

            result = control_gateway.process_event(sample_event)

            # Verify metadata is preserved
            assert result.session_context.metadata["channel"] == "test"
            assert result.session_context.metadata["event_metadata"]["custom_field"] == "custom_value"

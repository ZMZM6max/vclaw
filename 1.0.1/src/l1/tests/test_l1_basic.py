"""Tests for L1 User Interaction."""
import pytest
from unittest.mock import Mock, patch
import sys


from src.l1.l1_user_interaction import (
    UserInteraction, DataValidator,
    ValidationError
)
from src.l4 import MemoryKnowledge
from src.core.models import StandardEvent
from src.core.interfaces import MemoryInterface


class TestUserInteraction:
    """Tests for L1 User Interaction."""
    
    def test_telegram_message_normalization(self):
        """TC-L1-001: Telegram消息标准化"""
        # Arrange
        interaction = UserInteraction(memory=MemoryKnowledge())
        
        raw_data = {
            "update_id": 123456789,
            "message": {
                "message_id": 1,
                "from": {"id": 12345, "first_name": "User"},
                "chat": {"id": 12345, "type": "private"},
                "date": 1234567890,
                "text": "Hello bot"
            }
        }
        
        # Act
        event = interaction.receive_payload(raw_data, channel="telegram")
        
        # Assert
        assert event.channel == "telegram"
        assert event.user_id == "12345"
        assert event.content == "Hello bot"
        assert event.timestamp == 1234567890
    
    def test_validation_failure(self):
        """TC-L1-002: 数据验证失败"""
        # Arrange
        interaction = UserInteraction(memory=MemoryKnowledge())

        # Format is correct (Telegram format) but content is invalid (user_id too long)
        long_user_id = "x" * 300  # Exceeds 256 char limit
        raw_data = {
            "update_id": 123456789,
            "message": {
                "message_id": 1,
                "from": {"id": long_user_id, "first_name": "User"},
                "chat": {"id": long_user_id, "type": "private"},
                "date": 1234567890,
                "text": "Hello bot"
            }
        }

        # Act & Assert
        with pytest.raises(ValidationError):
            interaction.receive_payload(raw_data, channel="telegram")
    
    def test_websocket_message_processing(self):
        """TC-L1-003: WebSocket消息处理"""
        # Arrange
        interaction = UserInteraction(memory=MemoryKnowledge())
        
        raw_data = {
            "type": "message",
            "user_id": "ws_user_123",
            "content": "WebSocket test",
            "timestamp": 1234567890
        }
        
        # Act
        event = interaction.receive_payload(raw_data, channel="websocket")
        
        # Assert
        assert event.channel == "websocket"
        assert event.user_id == "ws_user_123"
        assert event.content == "WebSocket test"


class TestDataValidator:
    """Tests for data validation."""
    
    def test_valid_data(self):
        """Test validation with valid data"""
        from src.l1.l1_user_interaction import DataValidator

        validator = DataValidator()
        data = {
            "channel": "telegram",
            "user_id": "12345",
            "content": "Hello",
            "timestamp": 1234567890
        }

        assert validator.validate(data) is True

    def test_missing_required_field(self):
        """Test validation with missing field"""
        from src.l1.l1_user_interaction import DataValidator

        validator = DataValidator()
        data = {
            "channel": "telegram",
            # Missing user_id
            "content": "Hello",
            "timestamp": 1234567890
        }

        with pytest.raises(ValidationError):
            validator.validate(data)


class TestSessionManagement:
    """Tests for L1 session management (Phase 1)."""

    def test_first_request_creates_no_session_id(self):
        """TC-L1-SESSION-001: 首次请求，没有session_id，让L2创建"""
        # Arrange
        interaction = UserInteraction(memory=MemoryKnowledge())

        raw_data = {
            "update_id": 123,
            "message": {
                "message_id": 1,
                "from": {"id": "user_123", "first_name": "User"},
                "chat": {"id": "user_123", "type": "private"},
                "date": 1234567890,
                "text": "Hello"
            }
        }

        # Act
        event = interaction.receive_payload(raw_data, channel="telegram")

        # Assert
        assert event.metadata.get("session_id") is None
        assert event.metadata.get("is_new_session_request") is False

    def test_session_mapping_preserved_across_requests(self):
        """TC-L1-SESSION-002: 同一会话ID在多次请求中被保留"""
        # Arrange
        interaction = UserInteraction(memory=MemoryKnowledge())

        raw_data = {
            "update_id": 123,
            "message": {
                "message_id": 1,
                "from": {"id": "user_123", "first_name": "User"},
                "chat": {"id": "user_123", "type": "private"},
                "date": 1234567890,
                "text": "Hello"
            }
        }

        # First request
        event1 = interaction.receive_payload(raw_data, channel="telegram")
        assert event1.metadata.get("session_id") is None

        # Simulate L2 returning a session_id
        interaction.update_session_mapping("user_123", "session-abc-123", channel="telegram")

        # Second request
        raw_data["message"]["text"] = "Second message"
        event2 = interaction.receive_payload(raw_data, channel="telegram")

        # Assert: Same session_id
        assert event2.metadata.get("session_id") == "session-abc-123"
        assert event2.metadata.get("is_new_session_request") is False

    def test_new_session_command_clears_mapping(self):
        """TC-L1-SESSION-003: /new命令清除会话映射"""
        # Arrange
        interaction = UserInteraction(memory=MemoryKnowledge())

        # First, establish a session
        interaction.update_session_mapping("user_123", "session-abc-123", channel="telegram")
        assert interaction.get_user_session("user_123", channel="telegram") == "session-abc-123"

        # User sends /new command
        raw_data = {
            "update_id": 124,
            "message": {
                "message_id": 2,
                "from": {"id": "user_123", "first_name": "User"},
                "chat": {"id": "user_123", "type": "private"},
                "date": 1234567890,
                "text": "/new"
            }
        }

        # Act
        event = interaction.receive_payload(raw_data, channel="telegram")

        # Assert
        assert event.metadata.get("session_id") is None
        assert event.metadata.get("is_new_session_request") is True
        assert interaction.get_user_session("user_123", channel="telegram") is None  # Mapping cleared

    def test_various_new_session_commands(self):
        """TC-L1-SESSION-004: 多种新建会话命令"""
        commands = ["/new", "/reset", "/start", "新会话"]

        for cmd in commands:
            interaction = UserInteraction(memory=MemoryKnowledge())
            interaction.update_session_mapping("user_123", "old-session")

            raw_data = {
                "update_id": 123,
                "message": {
                    "message_id": 1,
                    "from": {"id": "user_123", "first_name": "User"},
                    "chat": {"id": "user_123", "type": "private"},
                    "date": 1234567890,
                    "text": cmd
                }
            }

            event = interaction.receive_payload(raw_data, channel="telegram")

            assert event.metadata.get("session_id") is None, f"Command {cmd} should clear session"
            assert event.metadata.get("is_new_session_request") is True, f"Command {cmd} should mark as new"

    def test_different_users_have_separate_sessions(self):
        """TC-L1-SESSION-005: 不同用户有独立的会话"""
        interaction = UserInteraction(memory=MemoryKnowledge())

        # User 1
        interaction.update_session_mapping("user_1", "session-user-1")

        # User 2
        interaction.update_session_mapping("user_2", "session-user-2")

        # Verify separation
        assert interaction.get_user_session("user_1") == "session-user-1"
        assert interaction.get_user_session("user_2") == "session-user-2"

        # User 1 creates new session
        assert interaction._get_session_id("user_1", "/new") == (None, True)
        assert interaction.get_user_session("user_1") is None
        assert interaction.get_user_session("user_2") == "session-user-2"  # Unchanged

    def test_update_session_mapping_dual_write(self):
        """Phase 3: update_session_mapping writes to memory and L4."""
        memory = Mock(spec=MemoryInterface)
        interaction = UserInteraction(memory=memory)
        interaction.update_session_mapping("user_123", "session-abc")
        assert interaction.get_user_session("user_123") == "session-abc"
        memory.save_user_preference.assert_called_once_with("user_123", "active_session_id", "session-abc")

    def test_new_command_clears_memory_and_l4(self):
        """Phase 3: /new clears both in-memory and L4 mapping."""
        memory = Mock(spec=MemoryInterface)
        memory.load_user_preference.return_value = None
        interaction = UserInteraction(memory=memory)
        interaction.update_session_mapping("user_123", "session-abc")
        raw_data = {
            "update_id": 124,
            "message": {
                "message_id": 2,
                "from": {"id": "user_123"},
                "chat": {"id": "user_123"},
                "date": 1234567890,
                "text": "/new"
            }
        }
        event = interaction.receive_payload(raw_data, channel="telegram")
        assert event.metadata.get("session_id") is None
        assert interaction.get_user_session("user_123") is None
        memory.save_user_preference.assert_called_with("user_123", "active_session_id", None)

    def test_l4_restore_on_cache_miss(self):
        """Phase 3: L4 restores session when memory cache misses."""
        memory = Mock(spec=MemoryInterface)
        memory.load_user_preference.return_value = "sess-123"
        interaction = UserInteraction(memory=memory)
        session_id = interaction.get_user_session("user_123")
        assert session_id == "sess-123"
        assert interaction._user_session_map["user_123"] == "sess-123"

    def test_l4_returns_none_no_mapping(self):
        """Phase 3: L4 returns None when no persistent mapping exists."""
        memory = Mock(spec=MemoryInterface)
        memory.load_user_preference.return_value = None
        interaction = UserInteraction(memory=memory)
        assert interaction.get_user_session("user_123") is None

    def test_no_memory_fallback_to_in_memory(self):
        """Phase 3: Without memory, behavior is pure in-memory (backward compatible)."""
        interaction = UserInteraction(memory=None)
        interaction.update_session_mapping("user_123", "session-abc")
        assert interaction.get_user_session("user_123") == "session-abc"

    def test_get_session_id_prefers_memory_over_l4(self):
        """Phase 3: Memory cache takes priority over L4 lookup."""
        memory = Mock(spec=MemoryInterface)
        memory.load_user_preference.return_value = "from-l4"
        interaction = UserInteraction(memory=memory)
        interaction._user_session_map["user_123"] = "from-memory"
        session_id = interaction.get_user_session("user_123")
        assert session_id == "from-memory"
        memory.load_user_preference.assert_not_called()

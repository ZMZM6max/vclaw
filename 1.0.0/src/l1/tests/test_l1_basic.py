"""Tests for L1 User Interaction."""
import pytest
from unittest.mock import Mock, patch
import sys


from src.l1.l1_user_interaction import (
    UserInteraction, DataValidator,
    ValidationError
)
from src.core.models import StandardEvent


class TestUserInteraction:
    """Tests for L1 User Interaction."""
    
    def test_telegram_message_normalization(self):
        """TC-L1-001: Telegram消息标准化"""
        # Arrange
        interaction = UserInteraction()
        
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
        interaction = UserInteraction()

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
        interaction = UserInteraction()
        
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
    """Tests for L1 session handling (L1 is stateless, session managed by L2)."""

    def test_standard_event_has_no_session_id(self):
        """TC-L1-SESSION-001: L1产出的StandardEvent中不包含session_id"""
        interaction = UserInteraction()

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

        event = interaction.receive_payload(raw_data, channel="telegram")

        assert "session_id" not in event.metadata
        assert "is_new_session_request" not in event.metadata

    def test_new_session_commands_passed_through(self):
        """TC-L1-SESSION-002: 新建会话命令作为普通消息原样传递给L2"""
        commands = ["/new", "/reset", "/start", "新会话"]

        for cmd in commands:
            interaction = UserInteraction()

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

            assert event.content == cmd
            assert "session_id" not in event.metadata
            assert "is_new_session_request" not in event.metadata

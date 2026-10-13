"""Tests for UserInteraction.send_response() and response context map."""
import pytest
from src.l1.l1_user_interaction import UserInteraction
from src.core.exceptions import UnsupportedChannelError


@pytest.fixture
def ui():
    return UserInteraction()


class TestSendResponse:
    def test_send_response_auto_detect_telegram(self, ui):
        raw_data = {
            "update_id": 1,
            "message": {
                "from": {"id": "u1"},
                "chat": {"id": 999},
                "date": 1234567890,
                "text": "Hello"
            }
        }
        ui.receive_payload(raw_data, channel="telegram")
        result = ui.send_response("u1", "Hi back")
        assert isinstance(result, dict)
        assert result["chat_id"] == 999
        assert result["text"] == "Hi back"

    def test_send_response_auto_detect_websocket(self, ui):
        raw_data = {"type": "msg", "user_id": "u1", "content": "Hello", "connection_id": "conn-1"}
        ui.receive_payload(raw_data, channel="websocket")
        result = ui.send_response("u1", "Hi back")
        assert isinstance(result, dict)
        assert result["type"] == "response"
        assert result["message"] == "Hi back"
        assert result["connection_id"] == "conn-1"

    def test_send_response_auto_detect_webhook(self, ui):
        raw_data = {"user_id": "u1", "content": "Hello", "headers": {}}
        ui.receive_payload(raw_data, channel="webhook")
        result = ui.send_response("u1", "Hi back")
        assert isinstance(result, tuple)
        assert result[0] == 200
        assert result[1]["response"] == "Hi back"

    def test_send_response_explicit_channel_override(self, ui):
        raw_data = {
            "update_id": 1,
            "message": {"from": {"id": "u1"}, "chat": {"id": 999}, "date": 1234567890, "text": "Hello"}
        }
        ui.receive_payload(raw_data, channel="telegram")
        result = ui.send_response("u1", "Hi back", channel="websocket", metadata={"connection_id": "c2"})
        assert result["type"] == "response"
        assert result["connection_id"] == "c2"

    def test_send_response_explicit_metadata_override(self, ui):
        raw_data = {
            "update_id": 1,
            "message": {"from": {"id": "u1"}, "chat": {"id": 111}, "date": 1234567890, "text": "Hello"}
        }
        ui.receive_payload(raw_data, channel="telegram")
        result = ui.send_response("u1", "Hi back", metadata={"chat_id": 999})
        assert result["chat_id"] == 999

    def test_send_response_unknown_channel_raises(self, ui):
        with pytest.raises(UnsupportedChannelError):
            ui.send_response("u1", "Hi", channel="slack")

    def test_send_response_no_context_fallback(self, ui):
        with pytest.raises(UnsupportedChannelError):
            ui.send_response("u1", "Hi")

    def test_response_context_overwritten_by_new_request(self, ui):
        telegram_data = {
            "update_id": 1,
            "message": {"from": {"id": "u1"}, "chat": {"id": 111}, "date": 1234567890, "text": "T"}
        }
        ws_data = {"type": "msg", "user_id": "u1", "content": "W", "connection_id": "conn-2"}
        ui.receive_payload(telegram_data, channel="telegram")
        ui.receive_payload(ws_data, channel="websocket")
        result = ui.send_response("u1", "Hi")
        assert result["type"] == "response"
        assert result["connection_id"] == "conn-2"

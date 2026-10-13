"""Tests for ErrorHandler business error routing (L3 error flow-back).

Covers stub formatting framework until L3 ErrorTranslator output structure
is finalized.
"""
import pytest
from src.l1.l1_user_interaction import ErrorHandler


@pytest.fixture
def error_handler():
    return ErrorHandler()


class TestBusinessErrorRouting:
    def test_handle_business_error_telegram(self, error_handler):
        error = {"error_message": "余额不足"}
        result = error_handler.handle_error(error, channel="telegram", metadata={"chat_id": 12345})
        assert isinstance(result, dict)
        assert result["chat_id"] == 12345
        assert result["text"] == "余额不足"

    def test_handle_business_error_websocket(self, error_handler):
        error = {"error_message": "余额不足"}
        result = error_handler.handle_error(error, channel="websocket")
        assert isinstance(result, dict)
        assert result["type"] == "error"
        assert result["message"] == "余额不足"
        assert "timestamp" in result

    def test_handle_business_error_webhook(self, error_handler):
        error = {"error_message": "余额不足"}
        result = error_handler.handle_error(error, channel="webhook")
        assert isinstance(result, tuple)
        assert result[0] == 500
        assert result[1] == {"error": "余额不足"}

    def test_handle_business_error_unknown_channel(self, error_handler):
        error = {"error_message": "余额不足"}
        result = error_handler.handle_error(error, channel="slack")
        assert result == {"error": "余额不足"}

    def test_handle_business_error_empty_dict(self, error_handler):
        error = {}
        result = error_handler.handle_error(error, channel="telegram")
        assert result["text"] == "Unknown error"

    def test_handle_business_error_missing_message_key(self, error_handler):
        error = {"code": 403}
        result = error_handler.handle_error(error, channel="telegram")
        assert result["text"] == "Unknown error"

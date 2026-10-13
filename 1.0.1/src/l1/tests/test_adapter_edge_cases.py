"""Tests for adapter and validator edge cases."""
import pytest
from src.l1.l1_user_interaction import (
    TelegramAdapter, WebSocketAdapter, HttpWebhookAdapter,
    DataValidator, EventNormalizer
)
from src.core.exceptions import ParseError, ValidationError, UnsupportedChannelError


# =============================================================================
# Adapter Edge Cases
# =============================================================================

class TestTelegramAdapterEdgeCases:
    def test_empty_data(self):
        adapter = TelegramAdapter()
        assert adapter.can_handle({}) is False

    def test_missing_message(self):
        adapter = TelegramAdapter()
        with pytest.raises(ParseError):
            adapter.parse({"update_id": 1})

    def test_missing_user_id(self):
        adapter = TelegramAdapter()
        with pytest.raises(ParseError):
            adapter.parse({"message": {"text": "hi"}})

    def test_missing_text(self):
        adapter = TelegramAdapter()
        with pytest.raises(ParseError):
            adapter.parse({"message": {"from": {"id": 1}}})


class TestWebSocketAdapterEdgeCases:
    def test_missing_user_id(self):
        adapter = WebSocketAdapter()
        with pytest.raises(ParseError):
            adapter.parse({"type": "msg", "content": "hi"})

    def test_missing_content(self):
        adapter = WebSocketAdapter()
        with pytest.raises(ParseError):
            adapter.parse({"type": "msg", "user_id": "u1"})


class TestWebhookAdapterEdgeCases:
    def test_no_matching_format(self):
        adapter = HttpWebhookAdapter()
        assert adapter.can_handle({"foo": "bar"}) is False

    def test_event_payload_missing_user_id(self):
        adapter = HttpWebhookAdapter()
        with pytest.raises(ParseError):
            adapter.parse({"event": "x", "payload": {"message": "hi"}})

    def test_simple_format_missing_user_id(self):
        adapter = HttpWebhookAdapter()
        with pytest.raises(ParseError):
            adapter.parse({"content": "hi", "headers": {}})


# =============================================================================
# DataValidator Edge Cases
# =============================================================================

class TestDataValidatorEdgeCases:
    @pytest.fixture
    def validator(self):
        return DataValidator()

    @pytest.mark.parametrize("content", [
        "<script>alert(1)</script>",
        "javascript:void(0)",
        "onclick=evil()",
    ])
    def test_xss_patterns(self, validator, content):
        with pytest.raises(ValidationError):
            validator.validate({"channel": "telegram", "user_id": "u1", "content": content})

    def test_user_id_too_long(self, validator):
        with pytest.raises(ValidationError):
            validator.validate({"channel": "telegram", "user_id": "x" * 257, "content": "hi"})

    def test_content_too_long(self, validator):
        with pytest.raises(ValidationError):
            validator.validate({"channel": "telegram", "user_id": "u1", "content": "x" * 10001})

    def test_timestamp_negative(self, validator):
        with pytest.raises(ValidationError):
            validator.validate({"channel": "telegram", "user_id": "u1", "content": "hi", "timestamp": -1})

    def test_timestamp_too_large(self, validator):
        with pytest.raises(ValidationError):
            validator.validate({"channel": "telegram", "user_id": "u1", "content": "hi", "timestamp": 4102444801})

    def test_timestamp_non_numeric(self, validator):
        with pytest.raises(ValidationError):
            validator.validate({"channel": "telegram", "user_id": "u1", "content": "hi", "timestamp": "bad"})

    def test_invalid_channel(self, validator):
        with pytest.raises(ValidationError):
            validator.validate({"channel": "email", "user_id": "u1", "content": "hi"})


# =============================================================================
# EventNormalizer Edge Cases
# =============================================================================

class TestEventNormalizerEdgeCases:
    def test_no_adapter_can_handle(self):
        normalizer = EventNormalizer()
        with pytest.raises(UnsupportedChannelError):
            normalizer.normalize({"unknown": "format"})

    def test_explicit_channel_not_found(self):
        normalizer = EventNormalizer()
        with pytest.raises(UnsupportedChannelError):
            normalizer.normalize({}, channel="email")

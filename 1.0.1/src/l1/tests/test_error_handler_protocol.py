"""Tests for ErrorHandler protocol-level formatting and retry boundaries."""
import pytest
from unittest.mock import Mock, patch
from src.l1.l1_user_interaction import ErrorHandler


@pytest.fixture
def error_handler():
    return ErrorHandler()


class TestProtocolFormatting:
    def test_handle_l1_internal_error_telegram(self, error_handler):
        error = ValueError("连接超时")
        result = error_handler.handle_error(error, channel="telegram", metadata={"chat_id": 123})
        assert isinstance(result, dict)
        assert result["chat_id"] == 123
        assert "连接超时" in result["text"]

    def test_handle_unsupported_error_type(self, error_handler):
        error = "raw string"
        result = error_handler.handle_error(error, channel="telegram")
        assert isinstance(result, dict)
        assert result["text"] == "raw string"


class TestRetryBoundaries:
    def test_retry_zero_max_retries(self):
        error_handler = ErrorHandler(max_retries=0)
        operation = Mock(side_effect=ConnectionError("fail"))
        with patch('src.l1.l1_user_interaction.time.sleep'):
            with pytest.raises(ConnectionError):
                error_handler.execute_with_retry(operation, retryable_exceptions=(ConnectionError,))
        assert operation.call_count == 1

    def test_retry_custom_delay(self):
        error_handler = ErrorHandler(max_retries=1, initial_delay=0.01)
        operation = Mock(side_effect=[ConnectionError("fail"), "success"])
        with patch('src.l1.l1_user_interaction.time.sleep') as mock_sleep:
            error_handler.execute_with_retry(
                operation,
                retryable_exceptions=(ConnectionError,)
            )
        assert mock_sleep.call_count == 1
        mock_sleep.assert_called_once_with(0.01)

    def test_retry_non_retryable_exception(self, error_handler):
        operation = Mock(side_effect=RuntimeError("fail"))
        with patch('src.l1.l1_user_interaction.time.sleep'):
            with pytest.raises(RuntimeError):
                error_handler.execute_with_retry(operation, retryable_exceptions=(ConnectionError,))
        assert operation.call_count == 1

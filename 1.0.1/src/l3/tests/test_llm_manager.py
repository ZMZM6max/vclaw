"""LLMManager Tests (TC-LLM-001 ~ 005)

Tests for LLMManager: multi-provider, retry, streaming.
Uses Mock for provider tests and real LLM for functional tests.
"""
import pytest
import sys
sys.path.insert(0, 'src')

from unittest.mock import MagicMock, patch
from src.l3.l3_orchestration import LLMManager, ProviderType
from src.core.exceptions import LLMError


class TestLLMManager:
    """LLMManager单元测试"""

    def test_complete_returns_string(self):
        """TC-LLM-001: complete() 返回文本回复"""
        manager = LLMManager()
        # Mock provider
        manager.provider = MagicMock()
        manager.provider.complete.return_value = "Hello, world!"

        result = manager.complete([{"role": "user", "content": "hi"}])

        assert isinstance(result, str)
        assert result == "Hello, world!"

    def test_complete_with_tools_returns_agent_action(self):
        """TC-LLM-002: 传入tools时返回AgentAction"""
        from src.core.models import AgentAction
        manager = LLMManager()
        manager.provider = MagicMock()
        manager.provider.complete.return_value = AgentAction(
            action="calculator",
            action_input={"expression": "1+1"},
            thought="Need to calculate"
        )

        tools = [{"type": "function", "function": {"name": "calculator"}}]
        result = manager.complete([{"role": "user", "content": "1+1"}], tools=tools)

        assert isinstance(result, AgentAction)
        assert result.action == "calculator"

    def test_stream_output(self):
        """TC-LLM-003: stream() 逐字输出"""
        manager = LLMManager()
        manager.provider = MagicMock()
        manager.provider.stream.return_value = iter(["He", "llo", "!"])

        result = list(manager.stream([{"role": "user", "content": "hi"}]))

        assert result == ["He", "llo", "!"]

    def test_retry_on_failure(self):
        """TC-LLM-004: 重试机制在失败后触发"""
        manager = LLMManager(max_retries=3, retry_delay=0.01)
        manager.provider = MagicMock()
        manager.provider.complete.side_effect = [
            LLMError("Network error"),
            LLMError("Network error"),
            "Success after retry"
        ]

        result = manager.complete([{"role": "user", "content": "hi"}])

        assert result == "Success after retry"
        assert manager.provider.complete.call_count == 3

    def test_retry_exhausted_raises(self):
        """TC-LLM-004: 重试耗尽后抛出异常"""
        manager = LLMManager(max_retries=2, retry_delay=0.01)
        manager.provider = MagicMock()
        manager.provider.complete.side_effect = LLMError("Persistent error")

        with pytest.raises(LLMError):
            manager.complete([{"role": "user", "content": "hi"}])

    def test_switch_provider(self):
        """TC-LLM-005: Provider切换正确"""
        manager = LLMManager()
        original_provider = manager.provider_name

        # Mock to avoid actual initialization
        with patch.object(manager, 'PROVIDERS', {ProviderType.OPENAI: MagicMock, ProviderType.KIMI: MagicMock}):
            manager.switch_provider("kimi")
            assert manager.provider_name == ProviderType.KIMI

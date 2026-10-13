"""MemoryAccessor Tests (TC-MA-001 ~ 004)

Mock-based tests for MemoryAccessor component.
"""
import pytest
import sys
sys.path.insert(0, 'src')

from unittest.mock import MagicMock
from src.l3.l3_orchestration import MemoryAccessor


class TestMemoryAccessor:
    """MemoryAccessor单元测试"""

    @pytest.fixture
    def mock_memory(self):
        """Create mock MemoryInterface."""
        memory = MagicMock()
        memory.search.return_value = ["Python is a programming language", "Python supports OOP"]
        memory.retrieve_history.return_value = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi!"},
            {"role": "user", "content": "What is Python?"}
        ]
        return memory

    def test_retrieve_knowledge(self, mock_memory):
        """TC-MA-001: 知识检索返回知识片段"""
        accessor = MemoryAccessor(memory=mock_memory)
        result = accessor.retrieve_for_query("Python", "session-001")

        assert "knowledge" in result
        assert len(result["knowledge"]) == 2
        mock_memory.search.assert_called_once_with("Python", top_k=3)

    def test_retrieve_history_summary(self, mock_memory):
        """TC-MA-002: 返回对话历史摘要"""
        accessor = MemoryAccessor(memory=mock_memory)
        result = accessor.retrieve_for_query("test", "session-001")

        assert "history_summary" in result
        assert "3 messages" in result["history_summary"]
        assert "related_queries" in result
        assert "What is Python?" in result["related_queries"]

    def test_format_context(self, mock_memory):
        """TC-MA-003: 上下文格式化正确"""
        accessor = MemoryAccessor(memory=mock_memory)
        retrieval = {
            "knowledge": ["Item 1", "Item 2"],
            "history_summary": "Recent conversation has 5 messages",
            "related_queries": ["q1", "q2"]
        }
        formatted = accessor.format_context(retrieval)

        assert "Relevant knowledge:" in formatted
        assert "Item 1" in formatted
        assert "Conversation:" in formatted
        assert "Related previous queries:" in formatted
        assert "q1" in formatted

    def test_memory_error_silent(self):
        """TC-MA-004: L4异常时静默处理，返回空结果"""
        memory = MagicMock()
        memory.search.side_effect = Exception("Vector store error")
        memory.retrieve_history.side_effect = Exception("History error")

        accessor = MemoryAccessor(memory=memory)
        result = accessor.retrieve_for_query("test", "session-001")

        assert result["knowledge"] == []
        assert result["history_summary"] == ""
        assert result["related_queries"] == []

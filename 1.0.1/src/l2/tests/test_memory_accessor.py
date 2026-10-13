"""Tests for MemoryAccessor component.

TC-MemoryAccessor-001: Retrieve relevant memories from L4
TC-MemoryAccessor-002: Return empty list when L4 has no results
TC-MemoryAccessor-003: Uses default MemoryKnowledge when no memory provided
"""
import sys
sys.path.insert(0, 'src')

from unittest.mock import Mock
from src.l2.l2_control_gateway import MemoryAccessor
from src.core.interfaces import MemoryInterface


class TestMemoryAccessor:
    """Tests for MemoryAccessor component."""

    def test_memory_accessor_retrieves_relevant_memories(self):
        """TC-MemoryAccessor-001: Retrieve relevant memories from L4."""
        # Mock L4 memory (returns List[str] like real MemoryKnowledge)
        mock_memory = Mock(spec=MemoryInterface)
        mock_memory.search.return_value = [
            "User likes Python",
            "User prefers concise answers"
        ]

        accessor = MemoryAccessor(memory=mock_memory)

        # Execute
        memories = accessor.retrieve_relevant(
            query="What programming language should I use?",
            user_id="user_123",
            top_k=5
        )

        # Verify
        assert len(memories) == 2
        assert "User likes Python" in memories
        assert mock_memory.search.called

        # Verify search was called with correct params
        call_args = mock_memory.search.call_args
        assert call_args.kwargs['top_k'] == 5
        assert call_args.kwargs['filters'] == {"user_id": "user_123"}

    def test_memory_accessor_returns_empty_list_when_no_results(self):
        """TC-MemoryAccessor-002: Return empty list when L4 has no results."""
        mock_memory = Mock()
        mock_memory.search.return_value = []

        accessor = MemoryAccessor(memory=mock_memory)
        memories = accessor.retrieve_relevant("query", "user_123")

        assert memories == []

    def test_memory_accessor_uses_default_memory(self):
        """TC-MemoryAccessor-003: Uses default MemoryKnowledge when no memory provided."""
        accessor = MemoryAccessor()

        # Should have default memory instance
        assert accessor.memory is not None

    def test_memory_accessor_filters_by_user_id(self):
        """Verify MemoryAccessor filters by user_id for privacy."""
        mock_memory = Mock()
        mock_memory.search.return_value = [
            "Memory for user 1"
        ]

        accessor = MemoryAccessor(memory=mock_memory)
        memories = accessor.retrieve_relevant(
            query="test query",
            user_id="user_1",
            top_k=3
        )

        # Verify filters contain user_id
        call_args = mock_memory.search.call_args
        assert call_args.kwargs['filters']['user_id'] == "user_1"

    def test_memory_accessor_respects_top_k(self):
        """Verify MemoryAccessor respects top_k parameter."""
        mock_memory = Mock()
        mock_memory.search.return_value = [
            "Memory 1",
            "Memory 2",
            "Memory 3"
        ]

        accessor = MemoryAccessor(memory=mock_memory)
        memories = accessor.retrieve_relevant(
            query="test",
            user_id="user_123",
            top_k=3
        )

        # Verify top_k is passed to search
        call_args = mock_memory.search.call_args
        assert call_args.kwargs['top_k'] == 3

    def test_memory_accessor_returns_strings_directly(self):
        """Verify MemoryAccessor returns string list from search directly."""
        mock_memory = Mock()
        mock_memory.search.return_value = [
            "Content 1",
            "Content 2"
        ]

        accessor = MemoryAccessor(memory=mock_memory)
        memories = accessor.retrieve_relevant("query", "user_123")

        # Should be list of strings returned directly from search
        assert isinstance(memories[0], str)
        assert memories[0] == "Content 1"
        assert memories[1] == "Content 2"

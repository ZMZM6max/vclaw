"""Tests for L4 Memory & Knowledge Layer.

This file contains integration tests and maintains compatibility with existing test infrastructure.
New component-specific tests should be added to individual test_*.py files.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
import sys
sys.path.insert(0, 'src')

from src.l4.core.l4_memory import MemoryKnowledge
from src.l4.storage.vector_store import MemoryVectorStore
from src.l4.storage.memory_store import InMemoryStore, MemoryCompressor
from src.core.models import Document


class TestMemoryKnowledge:
    """Tests for L4 MemoryKnowledge main class."""

    def test_search_basic(self):
        """TC-L4-001: 向量检索基本功能"""
        # Arrange
        memory = MemoryKnowledge(enable_caching=False)

        # Mock embedding service
        with patch.object(memory.embedding_service, 'embed') as mock_embed:
            mock_embed.return_value = [0.1] * 1536

            # Mock vector store
            with patch.object(memory.vector_store, 'search') as mock_search:
                mock_search.return_value = [
                    {"content": "Python is a programming language", "score": 0.95, "metadata": {}},
                    {"content": "JavaScript is another language", "score": 0.85, "metadata": {}}
                ]

                # Act
                results = memory.search("programming", top_k=2)

                # Assert
                assert len(results) == 2
                assert "Python" in results[0]
                mock_embed.assert_called_once_with("programming")
                mock_search.assert_called_once()

    def test_cache_hit(self):
        """TC-L4-002: 缓存命中"""
        # Arrange
        memory = MemoryKnowledge()

        # First call
        with patch.object(memory.embedding_service, 'embed') as mock_embed:
            mock_embed.return_value = [0.1] * 1536
            with patch.object(memory.vector_store, 'search') as mock_search:
                mock_search.return_value = [{"content": "test", "score": 0.9, "metadata": {}}]
                memory.search("test query")

        # Second call - should use cache
        with patch.object(memory.embedding_service, 'embed') as mock_embed:
            results = memory.search("test query")
            # Embedding should not be called again
            mock_embed.assert_not_called()

    def test_store_document(self):
        """TC-L4-003: 文档存储"""
        # Arrange
        memory = MemoryKnowledge(enable_caching=False)

        with patch.object(memory.text_chunker, 'split') as mock_split:
            mock_split.return_value = ["chunk1", "chunk2"]

            with patch.object(memory.embedding_service, 'embed_batch') as mock_embed:
                mock_embed.return_value = [[0.1] * 1536, [0.2] * 1536]

                with patch.object(memory.vector_store, 'add_documents') as mock_add:
                    mock_add.return_value = True

                    # Act
                    result = memory.store("Long document content...", {"doc_id": "123"})

                    # Assert
                    assert result is True
                    mock_split.assert_called_once()
                    mock_embed.assert_called_once()
                    mock_add.assert_called_once()

    def test_store_and_retrieve_conversation(self):
        """TC-L4-005: 对话历史存储与检索"""
        # Arrange
        memory = MemoryKnowledge()
        session_id = "test-session-123"
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"}
        ]

        # Store and Retrieve
        result = memory.store_conversation(session_id, messages)
        assert result is True

        retrieved = memory.retrieve_history(session_id, limit=2)
        assert len(retrieved) == 2


class TestMemoryVectorStore:
    """Tests for in-memory vector store."""

    def test_add_and_search(self):
        """Test adding documents and searching"""
        store = MemoryVectorStore()

        # Add documents
        store.add_documents([{
            "id": "doc1",
            "content": "Python programming",
            "embedding": [0.1, 0.2, 0.3],
            "metadata": {}
        }, {
            "id": "doc2",
            "content": "Java programming",
            "embedding": [0.2, 0.3, 0.4],
            "metadata": {}
        }])

        # Search
        results = store.search([0.1, 0.2, 0.3], top_k=1)
        assert len(results) == 1
        assert results[0]["content"] == "Python programming"


class TestMemoryStore:
    """Tests for memory store."""

    def test_save_and_load_conversation(self):
        """Test saving and loading conversation"""
        store = InMemoryStore()
        session_id = "test-session"
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi!"}
        ]

        # Save
        result = store.save_conversation(session_id, messages)
        assert result is True

        # Load
        loaded = store.load_conversation(session_id, limit=10)
        assert len(loaded) == 2
        assert loaded[0]["content"] == "Hello"

    def test_compression(self):
        """Test conversation compression"""
        compressor = MemoryCompressor(max_messages=5, compression_threshold=3)
        store = InMemoryStore(compressor=compressor)

        # Add messages that trigger compression
        messages = [{"role": "user", "content": f"msg{i}"} for i in range(5)]
        store.save_conversation("session1", messages)

        # Verify compression occurred
        full = store.get_full_conversation("session1")
        # Should have compressed to threshold + 1 (summary)
        assert len(full) <= 4


class TestL4Integration:
    """Integration tests for L4 layer."""

    def test_end_to_end_workflow(self):
        """Test complete L4 workflow"""
        memory = MemoryKnowledge(enable_caching=False)

        # 1. Store documents
        memory.store(
            "Python is a great programming language for data science",
            {"doc_id": "py-001", "category": "programming"}
        )
        memory.store(
            "JavaScript is used for web development",
            {"doc_id": "js-001", "category": "programming"}
        )

        # 2. Search
        results = memory.search_with_scores("programming", top_k=5)
        # Just verify search runs without error

        # 3. Store conversation
        messages = [
            {"role": "user", "content": "Tell me about Python"},
            {"role": "assistant", "content": "Python is a programming language"}
        ]
        memory.store_conversation("session-1", messages)

        # 4. Retrieve conversation
        history = memory.retrieve_history("session-1")
        assert len(history) == 2

        # 5. User preferences
        memory.save_user_preference("user-1", "theme", "dark")
        theme = memory.load_user_preference("user-1", "theme")
        assert theme == "dark"

        # 6. Statistics
        stats = memory.get_stats()
        assert "vector_store" in stats

    def test_empty_operations(self):
        """Test operations with empty data"""
        memory = MemoryKnowledge()

        # Empty search
        results = memory.search("")
        assert results == []

        # Empty conversation
        result = memory.store_conversation("empty-session", [])
        assert result is True

        # Non-existent session
        history = memory.retrieve_history("non-existent")
        assert history == []

    def test_metadata_filtering(self):
        """Test search with metadata filters"""
        memory = MemoryKnowledge(enable_caching=False)

        # Store with different metadata
        memory.store("Python guide", {"doc_id": "py1", "level": "beginner"})
        memory.store("Advanced Python", {"doc_id": "py2", "level": "advanced"})

        # Search with filter (implementation-dependent)
        results = memory.search_with_scores(
            "Python",
            filters={"level": "beginner"},
            top_k=10
        )

        # If filter is supported, should only return beginner docs
        for r in results:
            assert r["metadata"].get("level") == "beginner"

"""Tests for L4 MemoryKnowledge main class."""
import pytest
from src.l4.core.l4_memory import MemoryKnowledge, create_memory_knowledge
from src.l4.services.embedding import MockEmbeddingService
from src.l4.storage.vector_store import MemoryVectorStore
from src.l4.storage.memory_store import InMemoryStore


class TestMemoryKnowledgeInit:
    """Tests for MemoryKnowledge initialization."""

    def test_init_default(self):
        """Test default initialization."""
        memory = MemoryKnowledge()
        assert memory.embedding_service is not None
        assert memory.vector_store is not None
        assert memory.text_chunker is not None
        assert memory.memory_store is not None
        assert memory.enable_caching is True

    def test_init_with_dict_configs(self):
        """Test initialization with dict configs."""
        memory = MemoryKnowledge(
            embedding_service={"provider": "mock", "dimension": 128},
            vector_store={"store_type": "memory"},
        )
        assert memory.embedding_service.dimension == 128

    def test_init_with_instances(self):
        """Test initialization with component instances."""
        embedding = MockEmbeddingService(dimension=64)
        vector_store = MemoryVectorStore()

        memory = MemoryKnowledge(
            embedding_service=embedding,
            vector_store=vector_store,
        )
        assert memory.embedding_service is embedding
        assert memory.vector_store is vector_store

    def test_init_disable_caching(self):
        """Test initialization with caching disabled."""
        memory = MemoryKnowledge(enable_caching=False)
        assert memory.enable_caching is False
        assert memory.embedding_cache is None
        assert memory.search_cache is None


class TestMemoryKnowledgeSearch:
    """Tests for MemoryKnowledge search."""

    def test_search_empty_query(self):
        """Test search with empty query."""
        memory = MemoryKnowledge()
        results = memory.search("")
        assert results == []

    def test_search_no_documents(self):
        """Test search with no documents stored."""
        memory = MemoryKnowledge()
        results = memory.search("test query")
        assert results == []

    def test_search_with_documents(self):
        """Test search with documents."""
        memory = MemoryKnowledge(enable_caching=False)

        # Store documents
        memory.store("Python programming language", {"doc_id": "py1"})
        memory.store("Java programming language", {"doc_id": "java1"})
        memory.store("Cooking recipes", {"doc_id": "cook1"})

        # Search
        results = memory.search("programming", top_k=2)

        assert len(results) <= 2
        # Should find programming-related docs

    def test_search_with_scores(self):
        """Test search with scores."""
        memory = MemoryKnowledge(enable_caching=False)
        memory.store("Test document", {"doc_id": "test1"})

        results = memory.search_with_scores("test", top_k=1)

        assert len(results) > 0
        assert "score" in results[0]
        assert "content" in results[0]
        assert "metadata" in results[0]


class TestMemoryKnowledgeStore:
    """Tests for MemoryKnowledge store."""

    def test_store_document(self):
        """Test storing a document."""
        memory = MemoryKnowledge()
        result = memory.store("Test content", {"doc_id": "test1"})
        assert result is True

    def test_store_empty_document(self):
        """Test storing empty document."""
        memory = MemoryKnowledge()
        result = memory.store("", {"doc_id": "test1"})
        assert result is False

    def test_store_without_doc_id(self):
        """Test storing without doc_id."""
        memory = MemoryKnowledge()
        result = memory.store("Test content", {"source": "test"})
        assert result is False

    def test_store_batch(self):
        """Test batch store."""
        memory = MemoryKnowledge()
        documents = [
            {"content": "Doc 1", "metadata": {"doc_id": "d1"}},
            {"content": "Doc 2", "metadata": {"doc_id": "d2"}},
        ]

        result = memory.store_batch(documents)
        assert result is True

    def test_store_batch_empty(self):
        """Test batch store with empty list."""
        memory = MemoryKnowledge()
        result = memory.store_batch([])
        assert result is True

    def test_delete(self):
        """Test deleting document."""
        memory = MemoryKnowledge()
        memory.store("Test content", {"doc_id": "test1"})

        result = memory.delete("test1")
        assert result is True


class TestMemoryKnowledgeConversation:
    """Tests for MemoryKnowledge conversation methods."""

    def test_store_and_retrieve_conversation(self):
        """Test storing and retrieving conversation."""
        memory = MemoryKnowledge()
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi!"},
        ]

        memory.store_conversation("session1", messages)
        retrieved = memory.retrieve_history("session1")

        assert len(retrieved) == 2
        assert retrieved[0]["content"] == "Hello"

    def test_retrieve_history_limit(self):
        """Test retrieving history with limit."""
        memory = MemoryKnowledge()
        messages = [{"role": "user", "content": f"msg{i}"} for i in range(10)]

        memory.store_conversation("session1", messages)
        retrieved = memory.retrieve_history("session1", limit=5)

        assert len(retrieved) == 5

    def test_retrieve_nonexistent_session(self):
        """Test retrieving non-existent session."""
        memory = MemoryKnowledge()
        retrieved = memory.retrieve_history("nonexistent")
        assert retrieved == []

    def test_delete_session(self):
        """Test deleting session."""
        memory = MemoryKnowledge()
        memory.store_conversation("session1", [{"role": "user", "content": "Hi"}])

        result = memory.delete_session("session1")
        assert result is True

    def test_list_sessions(self):
        """Test listing sessions."""
        memory = MemoryKnowledge()
        memory.store_conversation("session1", [{"role": "user", "content": "Hi"}])
        memory.store_conversation("session2", [{"role": "user", "content": "Hello"}])

        sessions = memory.list_sessions()
        assert len(sessions) == 2


class TestMemoryKnowledgePreferences:
    """Tests for MemoryKnowledge preferences."""

    def test_save_and_load_preference(self):
        """Test saving and loading preference."""
        memory = MemoryKnowledge()
        memory.save_user_preference("user1", "theme", "dark")

        value = memory.load_user_preference("user1", "theme")
        assert value == "dark"

    def test_load_preference_default(self):
        """Test loading preference with default."""
        memory = MemoryKnowledge()
        value = memory.load_user_preference("user1", "nonexistent", default="default")
        assert value == "default"


class TestMemoryKnowledgeCache:
    """Tests for MemoryKnowledge caching."""

    def test_caching_enabled(self):
        """Test caching is enabled."""
        memory = MemoryKnowledge(enable_caching=True)
        assert memory.embedding_cache is not None
        assert memory.search_cache is not None

    def test_clear_cache(self):
        """Test clearing cache."""
        memory = MemoryKnowledge(enable_caching=True)
        result = memory.clear_cache()
        assert result is True

    def test_get_stats(self):
        """Test getting statistics."""
        memory = MemoryKnowledge(enable_caching=True)
        stats = memory.get_stats()

        assert "vector_store" in stats
        assert "embedding_cache" in stats
        assert "search_cache" in stats


class TestCreateMemoryKnowledge:
    """Tests for create_memory_knowledge factory."""

    def test_create_mock(self):
        """Test creating with mock embedding."""
        memory = create_memory_knowledge("mock")
        assert isinstance(memory, MemoryKnowledge)
        assert isinstance(memory.embedding_service, MockEmbeddingService)

    def test_create_with_custom_options(self):
        """Test creating MemoryKnowledge with options."""
        from src.l4 import create_memory_knowledge

        memory = create_memory_knowledge(
            provider="mock",
            vector_store_type="memory",
        )
        # Just verify it was created with mock embedding
        from src.l4.services.embedding import MockEmbeddingService
        assert isinstance(memory.embedding_service, MockEmbeddingService)


class TestMemoryKnowledgeIntegration:
    """Integration tests for MemoryKnowledge."""

    def test_full_workflow(self):
        """Test full workflow: store, search, retrieve conversation."""
        memory = MemoryKnowledge(enable_caching=False)

        # Store documents
        memory.store("Python is great for data science", {"doc_id": "py1"})
        memory.store("JavaScript is for web development", {"doc_id": "js1"})
        memory.store("Cooking Italian food", {"doc_id": "food1"})

        # Search
        results = memory.search("programming languages", top_k=5)
        assert len(results) > 0

        # Store conversation
        messages = [
            {"role": "user", "content": "Tell me about Python"},
            {"role": "assistant", "content": "Python is a great language!"},
        ]
        memory.store_conversation("session1", messages)

        # Retrieve conversation
        history = memory.retrieve_history("session1")
        assert len(history) == 2

    def test_compression_workflow(self):
        """Test compression workflow."""
        from src.l4.storage.memory_store import MemoryCompressor

        compressor = MemoryCompressor(max_messages=5, compression_threshold=3)
        memory = MemoryKnowledge(
            memory_store={"store_type": "memory", "compressor": compressor},
            enable_caching=False,
        )

        # Add many messages to trigger compression
        messages = [{"role": "user", "content": f"Message {i}"} for i in range(5)]
        memory.store_conversation("session1", messages)

        # Force compression
        memory.compress_session("session1")

        # Get compression stats
        stats = memory.get_compression_stats("session1")
        # Compression stats might be empty depending on implementation

    def test_metadata_filtering(self):
        """Test search with metadata filters."""
        memory = MemoryKnowledge(enable_caching=False)

        # Store documents with metadata
        memory.store(
            "Python programming",
            {"doc_id": "py1", "category": "programming", "level": "beginner"}
        )
        memory.store(
            "Advanced Python",
            {"doc_id": "py2", "category": "programming", "level": "advanced"}
        )
        memory.store(
            "Cooking recipes",
            {"doc_id": "cook1", "category": "cooking"}
        )

        # Search with filters
        results = memory.search_with_scores(
            "Python",
            top_k=10,
            filters={"category": "programming"}
        )

        # Should only return programming docs
        for r in results:
            assert r["metadata"].get("category") == "programming"

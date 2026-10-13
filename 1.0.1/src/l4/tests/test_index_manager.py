"""Tests for L4 Index Manager."""
import pytest
from src.l4.index.index_manager import (
    IndexManager,
    MemoryIndexManager,
    create_index_manager,
)


class TestMemoryIndexManager:
    """Tests for MemoryIndexManager."""

    def test_init_default(self):
        """Test default initialization."""
        manager = MemoryIndexManager()
        assert manager.indices == {}

    def test_create_index(self):
        """Test creating an index."""
        manager = MemoryIndexManager()
        result = manager.create_index("test-index", 128)

        assert result is True
        assert "test-index" in manager.indices
        assert manager.indices["test-index"]["dimension"] == 128

    def test_create_index_duplicate(self):
        """Test creating a duplicate index fails."""
        manager = MemoryIndexManager()
        manager.create_index("test-index", 128)

        result = manager.create_index("test-index", 128)
        assert result is False

    def test_delete_index(self):
        """Test deleting an index."""
        manager = MemoryIndexManager()
        manager.create_index("test-index", 128)

        result = manager.delete_index("test-index")
        assert result is True
        assert "test-index" not in manager.indices

    def test_delete_index_nonexistent(self):
        """Test deleting a non-existent index."""
        manager = MemoryIndexManager()
        result = manager.delete_index("nonexistent")
        assert result is False

    def test_list_indices(self):
        """Test listing indices."""
        manager = MemoryIndexManager()
        manager.create_index("index1", 128)
        manager.create_index("index2", 256)

        indices = manager.list_indices()
        assert len(indices) == 2
        names = [idx["name"] for idx in indices]
        assert "index1" in names
        assert "index2" in names

    def test_list_indices_empty(self):
        """Test listing indices when empty."""
        manager = MemoryIndexManager()
        indices = manager.list_indices()
        assert indices == []

    def test_get_index_stats(self):
        """Test getting index statistics."""
        manager = MemoryIndexManager()
        manager.create_index("test-index", 128)

        stats = manager.get_index_stats("test-index")
        assert stats["exists"] is True
        assert stats["dimension"] == 128

    def test_get_index_stats_nonexistent(self):
        """Test getting stats for non-existent index."""
        manager = MemoryIndexManager()
        stats = manager.get_index_stats("nonexistent")
        assert stats["exists"] is False

    def test_optimize_index(self):
        """Test optimizing an index."""
        manager = MemoryIndexManager()
        manager.create_index("test-index", 128)

        result = manager.optimize_index("test-index")
        assert result is True

    def test_optimize_index_nonexistent(self):
        """Test optimizing a non-existent index."""
        manager = MemoryIndexManager()
        result = manager.optimize_index("nonexistent")
        assert result is False

    def test_index_exists(self):
        """Test checking if an index exists."""
        manager = MemoryIndexManager()
        manager.create_index("test-index", 128)

        assert manager.index_exists("test-index") is True
        assert manager.index_exists("nonexistent") is False

    def test_update_index(self):
        """Test updating an index with documents."""
        manager = MemoryIndexManager()
        manager.create_index("test-index", 128)

        documents = [
            {"id": "doc1", "content": "Test", "embedding": [0.1] * 128},
            {"id": "doc2", "content": "Test 2", "embedding": [0.2] * 128},
        ]
        result = manager.update_index("test-index", documents)

        assert result is True
        assert manager.indices["test-index"]["document_count"] == 2
        assert "updated_at" in manager.indices["test-index"]

    def test_update_index_nonexistent(self):
        """Test updating a non-existent index."""
        manager = MemoryIndexManager()
        result = manager.update_index("nonexistent", [])
        assert result is False

    def test_update_index_empty_documents(self):
        """Test updating an index with empty documents."""
        manager = MemoryIndexManager()
        manager.create_index("test-index", 128)

        result = manager.update_index("test-index", [])
        assert result is True
        assert manager.indices["test-index"]["document_count"] == 0

    def test_update_document_count(self):
        """Test manually updating document count."""
        manager = MemoryIndexManager()
        manager.create_index("test-index", 128)

        manager.update_document_count("test-index", 10)
        assert manager.indices["test-index"]["document_count"] == 10


class TestCreateIndexManager:
    """Tests for create_index_manager factory."""

    def test_create_memory(self):
        """Test creating memory index manager."""
        manager = create_index_manager("memory")
        assert isinstance(manager, MemoryIndexManager)

    def test_create_case_insensitive(self):
        """Test factory is case insensitive."""
        manager1 = create_index_manager("MEMORY")
        manager2 = create_index_manager("Memory")
        assert isinstance(manager1, MemoryIndexManager)
        assert isinstance(manager2, MemoryIndexManager)

    def test_create_unsupported(self):
        """Test creating unsupported manager raises error."""
        with pytest.raises(ValueError) as exc_info:
            create_index_manager("unsupported")
        assert "Unsupported index manager type" in str(exc_info.value)


class TestIndexManagerAbstract:
    """Tests for IndexManager abstract base class."""

    def test_cannot_instantiate(self):
        """Test that IndexManager cannot be instantiated directly."""
        with pytest.raises(TypeError):
            IndexManager()

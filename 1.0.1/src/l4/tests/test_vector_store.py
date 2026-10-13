"""Tests for L4 Vector Store."""
import pytest
import numpy as np
from src.l4.storage.vector_store import (
    MemoryVectorStore,
    PineconeVectorStore,
    VectorStore,
    VectorStoreError,
    create_vector_store,
)


class TestMemoryVectorStore:
    """Tests for MemoryVectorStore."""

    def test_init_default(self):
        """Test default initialization."""
        store = MemoryVectorStore()
        assert store.dimension is None
        assert store.documents == {}

    def test_init_with_dimension(self):
        """Test initialization with dimension."""
        store = MemoryVectorStore(dimension=128)
        assert store.dimension == 128

    def test_add_documents(self):
        """Test adding documents."""
        store = MemoryVectorStore()
        documents = [
            {
                "id": "doc1",
                "content": "Test content",
                "embedding": [0.1, 0.2, 0.3],
                "metadata": {"source": "test"}
            }
        ]

        result = store.add_documents(documents)
        assert result is True
        assert "doc1" in store.documents
        assert store.documents["doc1"]["content"] == "Test content"

    def test_add_documents_without_id(self):
        """Test adding documents without ID."""
        store = MemoryVectorStore()
        documents = [
            {
                "content": "Test content",
                "embedding": [0.1, 0.2, 0.3],
            }
        ]

        result = store.add_documents(documents)
        assert result is True
        # Should skip document without ID
        assert len(store.documents) == 0

    def test_add_documents_dimension_validation(self):
        """Test dimension validation when adding documents."""
        store = MemoryVectorStore(dimension=128)
        documents = [
            {
                "id": "doc1",
                "content": "Test",
                "embedding": [0.1, 0.2],  # Wrong dimension
            }
        ]

        result = store.add_documents(documents)
        assert result is True
        # Should skip document with wrong dimension
        assert len(store.documents) == 0

    def test_search_empty_store(self):
        """Test search on empty store."""
        store = MemoryVectorStore()
        results = store.search([0.1, 0.2, 0.3])
        assert results == []

    def test_search_basic(self):
        """Test basic search functionality."""
        store = MemoryVectorStore()
        documents = [
            {
                "id": "doc1",
                "content": "First document",
                "embedding": [1.0, 0.0, 0.0],
                "metadata": {"source": "test"}
            },
            {
                "id": "doc2",
                "content": "Second document",
                "embedding": [0.0, 1.0, 0.0],
                "metadata": {"source": "test"}
            },
        ]
        store.add_documents(documents)

        # Search with query similar to doc1
        results = store.search([1.0, 0.0, 0.0], top_k=1)

        assert len(results) == 1
        assert results[0]["id"] == "doc1"
        assert results[0]["content"] == "First document"
        assert "score" in results[0]

    def test_search_top_k(self):
        """Test search with top_k limit."""
        store = MemoryVectorStore()
        documents = [
            {"id": f"doc{i}", "content": f"Content {i}", "embedding": [i/10, 0, 0]}
            for i in range(10)
        ]
        store.add_documents(documents)

        results = store.search([1.0, 0, 0], top_k=3)
        assert len(results) == 3

    def test_search_with_filters(self):
        """Test search with metadata filters."""
        store = MemoryVectorStore()
        documents = [
            {
                "id": "doc1",
                "content": "First",
                "embedding": [1.0, 0, 0],
                "metadata": {"category": "A"}
            },
            {
                "id": "doc2",
                "content": "Second",
                "embedding": [1.0, 0, 0],
                "metadata": {"category": "B"}
            },
        ]
        store.add_documents(documents)

        results = store.search([1.0, 0, 0], filters={"category": "A"})
        assert len(results) == 1
        assert results[0]["id"] == "doc1"

    def test_search_with_range_filters(self):
        """Test search with range filters."""
        store = MemoryVectorStore()
        documents = [
            {
                "id": "doc1",
                "content": "First",
                "embedding": [1.0, 0, 0],
                "metadata": {"score": 5}
            },
            {
                "id": "doc2",
                "content": "Second",
                "embedding": [1.0, 0, 0],
                "metadata": {"score": 10}
            },
        ]
        store.add_documents(documents)

        results = store.search([1.0, 0, 0], filters={"score": {"gte": 8}})
        assert len(results) == 1
        assert results[0]["id"] == "doc2"

    def test_delete(self):
        """Test deleting documents."""
        store = MemoryVectorStore()
        documents = [
            {"id": "doc1", "content": "First", "embedding": [1.0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]},
            {"id": "doc2", "content": "Second", "embedding": [0, 1.0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]},
        ]
        store.add_documents(documents)

        result = store.delete(["doc1"])
        assert result is True
        assert "doc1" not in store.documents
        assert "doc2" in store.documents

    def test_delete_nonexistent(self):
        """Test deleting non-existent documents."""
        store = MemoryVectorStore()
        # Should not raise error
        result = store.delete(["nonexistent"])
        assert result is True

    def test_get_collection_stats(self):
        """Test getting collection statistics."""
        store = MemoryVectorStore(dimension=128)
        documents = [
            {"id": "doc1", "content": "First", "embedding": [1.0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]},
            {"id": "doc2", "content": "Second", "embedding": [0, 1.0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]},
        ]
        store.add_documents(documents)

        stats = store.get_collection_stats()
        assert stats["document_count"] == 2
        assert stats["dimension"] == 128
        assert stats["store_type"] == "memory"


class TestCosineSimilarity:
    """Tests for cosine similarity calculation."""

    def test_identical_vectors(self):
        """Test similarity of identical vectors."""
        v = [1.0, 2.0, 3.0]
        result = VectorStore.cosine_similarity(v, v)
        assert result == pytest.approx(1.0, abs=1e-6)

    def test_orthogonal_vectors(self):
        """Test similarity of orthogonal vectors."""
        v1 = [1.0, 0.0, 0.0]
        v2 = [0.0, 1.0, 0.0]
        result = VectorStore.cosine_similarity(v1, v2)
        assert result == pytest.approx(0.0, abs=1e-6)

    def test_opposite_vectors(self):
        """Test similarity of opposite vectors."""
        v1 = [1.0, 2.0, 3.0]
        v2 = [-1.0, -2.0, -3.0]
        result = VectorStore.cosine_similarity(v1, v2)
        assert result == pytest.approx(-1.0, abs=1e-6)

    def test_zero_vector(self):
        """Test similarity with zero vector."""
        v1 = [1.0, 2.0, 3.0]
        v2 = [0.0, 0.0, 0.0]
        result = VectorStore.cosine_similarity(v1, v2)
        assert result == 0.0

    def test_similar_vectors(self):
        """Test similarity of similar vectors."""
        v1 = [1.0, 2.0, 3.0]
        v2 = [1.1, 2.1, 3.1]
        result = VectorStore.cosine_similarity(v1, v2)
        assert 0.9 < result <= 1.0


class TestCreateVectorStore:
    """Tests for create_vector_store factory."""

    def test_create_memory(self):
        """Test creating memory store."""
        store = create_vector_store("memory", dimension=128)
        assert isinstance(store, MemoryVectorStore)
        assert store.dimension == 128

    def test_create_case_insensitive(self):
        """Test factory is case insensitive."""
        store1 = create_vector_store("MEMORY")
        store2 = create_vector_store("Memory")
        assert isinstance(store1, MemoryVectorStore)
        assert isinstance(store2, MemoryVectorStore)

    def test_create_unsupported(self):
        """Test creating unsupported store raises error."""
        with pytest.raises(ValueError) as exc_info:
            create_vector_store("unsupported")
        assert "Unsupported vector store type" in str(exc_info.value)

    def test_create_pinecone_raises(self):
        """Test creating pinecone store raises NotImplementedError."""
        with pytest.raises(NotImplementedError) as exc_info:
            create_vector_store("pinecone")
        assert "PineconeVectorStore is not yet implemented" in str(exc_info.value)


class TestPineconeVectorStore:
    """Tests for PineconeVectorStore stub."""

    def test_init_raises_not_implemented(self):
        """Test that PineconeVectorStore init raises NotImplementedError."""
        with pytest.raises(NotImplementedError) as exc_info:
            PineconeVectorStore()
        assert "PineconeVectorStore is not yet implemented" in str(exc_info.value)

    def test_init_raises_with_params(self):
        """Test that PineconeVectorStore raises even with parameters."""
        with pytest.raises(NotImplementedError) as exc_info:
            PineconeVectorStore(
                api_key="test-key",
                environment="us-east-1",
                index_name="test-index",
                dimension=1536,
            )
        assert "PineconeVectorStore is not yet implemented" in str(exc_info.value)


class TestVectorStoreIntegration:
    """Integration tests for vector stores."""

    def test_add_and_search_roundtrip(self):
        """Test add and search roundtrip."""
        store = MemoryVectorStore()

        # Add documents with distinct embeddings
        documents = [
            {"id": "doc1", "content": "Content 1", "embedding": [1.0, 0.0, 0.0]},
            {"id": "doc2", "content": "Content 2", "embedding": [0.0, 1.0, 0.0]},
            {"id": "doc3", "content": "Content 3", "embedding": [0.0, 0.0, 1.0]},
        ]
        store.add_documents(documents)

        # Search with query similar to doc1
        results = store.search([1.0, 0.0, 0.0], top_k=1)

        assert len(results) == 1
        # doc1 has embedding [1.0, 0, 0], should be most similar
        assert results[0]["id"] == "doc1"

    def test_search_results_sorted(self):
        """Test search results are sorted by score."""
        store = MemoryVectorStore()
        documents = [
            {"id": "doc1", "content": "First", "embedding": [0.5, 0, 0]},
            {"id": "doc2", "content": "Second", "embedding": [1.0, 0, 0]},
            {"id": "doc3", "content": "Third", "embedding": [0.1, 0, 0]},
        ]
        store.add_documents(documents)

        results = store.search([1.0, 0, 0], top_k=3)

        scores = [r["score"] for r in results]
        assert scores == sorted(scores, reverse=True)

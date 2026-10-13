"""Tests for L4 Embedding Service."""
import pytest
import os
from src.l4.services.embedding import (
    MockEmbeddingService,
    OpenAIEmbeddingService,
    SentenceTransformerService,
    create_embedding_service,
    EmbeddingError,
)


class TestMockEmbeddingService:
    """Tests for MockEmbeddingService."""

    def test_init_default_dimension(self):
        """Test default dimension initialization."""
        service = MockEmbeddingService()
        assert service.dimension == 1536

    def test_init_custom_dimension(self):
        """Test custom dimension initialization."""
        service = MockEmbeddingService(dimension=768)
        assert service.dimension == 768

    def test_embed_returns_correct_dimension(self):
        """Test embed returns vector of correct dimension."""
        service = MockEmbeddingService(dimension=128)
        result = service.embed("test text")
        assert len(result) == 128
        assert all(isinstance(x, float) for x in result)

    def test_embed_deterministic(self):
        """Test embed is deterministic for same input."""
        service = MockEmbeddingService()
        result1 = service.embed("hello world")
        result2 = service.embed("hello world")
        assert result1 == result2

    def test_embed_different_inputs(self):
        """Test different inputs produce different embeddings."""
        service = MockEmbeddingService()
        result1 = service.embed("hello")
        result2 = service.embed("world")
        assert result1 != result2

    def test_embed_batch(self):
        """Test batch embedding."""
        service = MockEmbeddingService(dimension=64)
        texts = ["text 1", "text 2", "text 3"]
        results = service.embed_batch(texts)

        assert len(results) == 3
        assert all(len(r) == 64 for r in results)

    def test_embed_batch_empty(self):
        """Test batch embedding with empty list."""
        service = MockEmbeddingService()
        results = service.embed_batch([])
        assert results == []

    def test_embed_batch_empty_text(self):
        """Test batch embedding with empty text in list."""
        service = MockEmbeddingService(dimension=64)
        texts = ["text", "", "another"]
        results = service.embed_batch(texts)

        assert len(results) == 3
        # Empty text should still produce embedding
        assert len(results[1]) == 64


class TestSentenceTransformerService:
    """Tests for SentenceTransformerService."""

    def test_init_default_model(self):
        """Test initialization with default model."""
        # This test might be slow due to model loading
        pytest.skip("Skipping model loading test - requires download")

    def test_init_invalid_model(self):
        """Test initialization with invalid model."""
        pytest.skip("Skipping model loading test")


class TestOpenAIEmbeddingService:
    """Tests for OpenAIEmbeddingService."""

    def test_init_no_api_key(self):
        """Test initialization without API key raises error."""
        # Clear any existing API key
        original_key = os.environ.pop("OPENAI_API_KEY", None)
        try:
            with pytest.raises(ValueError) as exc_info:
                OpenAIEmbeddingService()
            assert "API key is required" in str(exc_info.value)
        finally:
            if original_key:
                os.environ["OPENAI_API_KEY"] = original_key

    def test_init_invalid_model(self):
        """Test initialization with invalid model."""
        with pytest.raises(ValueError) as exc_info:
            OpenAIEmbeddingService(api_key="fake-key", model="invalid-model")
        assert "Unsupported model" in str(exc_info.value)

    def test_dimension_property(self):
        """Test dimension property for different models."""
        # Just test the logic without actual API calls
        pytest.skip("Skipping API test")


class TestCreateEmbeddingService:
    """Tests for create_embedding_service factory."""

    def test_create_mock(self):
        """Test creating mock service."""
        service = create_embedding_service("mock", dimension=256)
        assert isinstance(service, MockEmbeddingService)
        assert service.dimension == 256

    def test_create_mock_case_insensitive(self):
        """Test factory is case insensitive."""
        service1 = create_embedding_service("MOCK")
        service2 = create_embedding_service("Mock")
        assert isinstance(service1, MockEmbeddingService)
        assert isinstance(service2, MockEmbeddingService)

    def test_create_unsupported_provider(self):
        """Test creating unsupported provider raises error."""
        with pytest.raises(ValueError) as exc_info:
            create_embedding_service("unsupported")
        assert "Unsupported embedding provider" in str(exc_info.value)

    def test_create_openai(self):
        """Test creating OpenAI service."""
        # Skip if no API key
        if not os.getenv("OPENAI_API_KEY"):
            pytest.skip("OPENAI_API_KEY not set")

        service = create_embedding_service("openai", model="text-embedding-3-small")
        assert isinstance(service, OpenAIEmbeddingService)
        assert service.dimension == 1536

    def test_create_sentence_transformers(self):
        """Test creating sentence transformers service."""
        pytest.skip("Skipping model loading test")


class TestEmbeddingIntegration:
    """Integration tests for embedding services."""

    def test_mock_service_embedding_range(self):
        """Test mock embeddings are in valid range."""
        service = MockEmbeddingService()
        result = service.embed("test")

        # Mock uses random.random() which returns [0, 1)
        assert all(0 <= x < 1 for x in result)

    def test_batch_consistency(self):
        """Test batch embedding is consistent with individual."""
        service = MockEmbeddingService()
        texts = ["hello", "world", "test"]

        batch_results = service.embed_batch(texts)
        individual_results = [service.embed(t) for t in texts]

        assert batch_results == individual_results

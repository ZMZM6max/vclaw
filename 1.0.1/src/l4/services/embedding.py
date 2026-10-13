"""L4: Embedding Service - Text to vector embedding generation."""
from abc import ABC, abstractmethod
from typing import List, Optional
import os
import logging

logger = logging.getLogger(__name__)


class EmbeddingService(ABC):
    """Abstract base class for embedding services."""

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Return the embedding dimension."""
        pass

    @abstractmethod
    def embed(self, text: str) -> List[float]:
        """Generate embedding for a single text.

        Args:
            text: Input text to embed

        Returns:
            List of float values representing the embedding vector
        """
        pass

    @abstractmethod
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts.

        Args:
            texts: List of input texts to embed

        Returns:
            List of embedding vectors
        """
        pass


class MockEmbeddingService(EmbeddingService):
    """Mock embedding service for testing."""

    def __init__(self, dimension: int = 1536):
        self._dimension = dimension

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed(self, text: str) -> List[float]:
        """Generate mock embedding (deterministic based on text)."""
        # Create a simple deterministic embedding based on text hash
        import hashlib
        hash_val = int(hashlib.md5(text.encode()).hexdigest(), 16)
        import random
        rng = random.Random(hash_val)
        return [rng.random() for _ in range(self._dimension)]

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate mock embeddings for batch."""
        return [self.embed(text) for text in texts]


class OpenAIEmbeddingService(EmbeddingService):
    """OpenAI embedding service using OpenAI API."""

    SUPPORTED_MODELS = {
        "text-embedding-3-small": 1536,
        "text-embedding-3-large": 3072,
        "text-embedding-ada-002": 1536,
    }

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "text-embedding-3-small",
        base_url: Optional[str] = None,
    ):
        """Initialize OpenAI embedding service.

        Args:
            api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)
            model: Model name to use
            base_url: Optional custom base URL for API
        """
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError(
                "openai package is required for OpenAIEmbeddingService. "
                "Install with: pip install openai"
            )

        if model not in self.SUPPORTED_MODELS:
            raise ValueError(
                f"Unsupported model: {model}. "
                f"Supported models: {list(self.SUPPORTED_MODELS.keys())}"
            )

        self.model = model
        self._dimension = self.SUPPORTED_MODELS[model]

        api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError(
                "OpenAI API key is required. "
                "Set OPENAI_API_KEY environment variable or pass api_key parameter."
            )

        client_kwargs = {"api_key": api_key}
        if base_url:
            client_kwargs["base_url"] = base_url

        self.client = OpenAI(**client_kwargs)
        logger.info(f"Initialized OpenAIEmbeddingService with model: {model}")

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed(self, text: str) -> List[float]:
        """Generate embedding using OpenAI API."""
        if not text or not text.strip():
            # Return zero vector for empty text
            return [0.0] * self._dimension

        try:
            response = self.client.embeddings.create(
                model=self.model,
                input=text.strip()
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"OpenAI embedding error: {e}")
            raise EmbeddingError(f"Failed to generate embedding: {e}") from e

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts using OpenAI API."""
        if not texts:
            return []

        # Filter out empty texts and track their positions
        valid_texts = []
        empty_indices = []
        for i, text in enumerate(texts):
            if text and text.strip():
                valid_texts.append(text.strip())
            else:
                empty_indices.append(i)

        if not valid_texts:
            return [[0.0] * self._dimension for _ in texts]

        try:
            response = self.client.embeddings.create(
                model=self.model,
                input=valid_texts
            )

            # Reconstruct results with empty vectors in correct positions
            valid_embeddings = [item.embedding for item in response.data]
            results = []
            valid_idx = 0

            for i in range(len(texts)):
                if i in empty_indices:
                    results.append([0.0] * self._dimension)
                else:
                    results.append(valid_embeddings[valid_idx])
                    valid_idx += 1

            return results
        except Exception as e:
            logger.error(f"OpenAI batch embedding error: {e}")
            raise EmbeddingError(f"Failed to generate batch embeddings: {e}") from e


class SentenceTransformerService(EmbeddingService):
    """Local embedding service using sentence-transformers."""

    DEFAULT_MODEL = "all-MiniLM-L6-v2"
    DEFAULT_DIMENSION = 384

    def __init__(
        self,
        model_name: Optional[str] = None,
        device: Optional[str] = None,
        cache_folder: Optional[str] = None,
    ):
        """Initialize sentence transformer embedding service.

        Args:
            model_name: Model name from sentence-transformers
            device: Device to use ('cpu', 'cuda', etc.)
            cache_folder: Folder to cache downloaded models
        """
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            raise ImportError(
                "sentence-transformers package is required. "
                "Install with: pip install sentence-transformers"
            )

        self.model_name = model_name or self.DEFAULT_MODEL

        model_kwargs = {}
        if cache_folder:
            model_kwargs["cache_folder"] = cache_folder

        try:
            self.model = SentenceTransformer(self.model_name, device=device, **model_kwargs)
            self._dimension = self.model.get_sentence_embedding_dimension()
            logger.info(
                f"Initialized SentenceTransformerService with model: {self.model_name} "
                f"(dim: {self._dimension})"
            )
        except Exception as e:
            logger.error(f"Failed to load model {self.model_name}: {e}")
            raise EmbeddingError(f"Failed to load sentence transformer model: {e}") from e

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed(self, text: str) -> List[float]:
        """Generate embedding using sentence-transformers."""
        if not text or not text.strip():
            return [0.0] * self._dimension

        try:
            embedding = self.model.encode(text.strip(), convert_to_numpy=True)
            return embedding.tolist()
        except Exception as e:
            logger.error(f"Sentence transformer embedding error: {e}")
            raise EmbeddingError(f"Failed to generate embedding: {e}") from e

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts."""
        if not texts:
            return []

        # Handle empty texts
        valid_texts = []
        empty_indices = []
        for i, text in enumerate(texts):
            if text and text.strip():
                valid_texts.append(text.strip())
            else:
                empty_indices.append(i)

        if not valid_texts:
            return [[0.0] * self._dimension for _ in texts]

        try:
            embeddings = self.model.encode(valid_texts, convert_to_numpy=True)

            # Reconstruct results
            results = []
            valid_idx = 0

            for i in range(len(texts)):
                if i in empty_indices:
                    results.append([0.0] * self._dimension)
                else:
                    results.append(embeddings[valid_idx].tolist())
                    valid_idx += 1

            return results
        except Exception as e:
            logger.error(f"Sentence transformer batch embedding error: {e}")
            raise EmbeddingError(f"Failed to generate batch embeddings: {e}") from e


class EmbeddingError(Exception):
    """Exception raised for embedding service errors."""
    pass


def create_embedding_service(
    provider: str = "mock",
    **kwargs
) -> EmbeddingService:
    """Factory function to create embedding service.

    Args:
        provider: Provider type ('openai', 'sentence-transformers', 'mock')
        **kwargs: Provider-specific arguments

    Returns:
        EmbeddingService instance

    Raises:
        ValueError: If provider is not supported
    """
    provider = provider.lower()

    if provider == "openai":
        return OpenAIEmbeddingService(**kwargs)
    elif provider in ("sentence-transformers", "sentence_transformers", "local"):
        return SentenceTransformerService(**kwargs)
    elif provider == "mock":
        return MockEmbeddingService(**kwargs)
    else:
        raise ValueError(
            f"Unsupported embedding provider: {provider}. "
            f"Supported: openai, sentence-transformers, mock"
        )

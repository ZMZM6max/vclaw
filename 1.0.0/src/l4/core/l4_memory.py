"""L4: Memory & Knowledge Layer - Vector search, memory storage, and RAG.

This module provides the L4 layer implementation for the VClaw system,
responsible for:
- Text embedding generation
- Vector storage and similarity search
- Text chunking and processing
- Conversation history storage with compression
- Caching for performance optimization

Example:
    >>> from src.l4.l4_memory import MemoryKnowledge
    >>> memory = MemoryKnowledge()
    >>> memory.store("Python is a programming language", {"doc_id": "py-001"})
    >>> results = memory.search("programming languages", top_k=3)
"""
from typing import List, Dict, Any, Optional, Union
from src.core.models import Document
from src.core.interfaces import MemoryInterface

# Import submodules
from src.l4.services.embedding import (
    EmbeddingService,
    create_embedding_service,
    EmbeddingError,
)
from src.l4.storage.vector_store import (
    VectorStore,
    create_vector_store,
    VectorStoreError,
)
from src.l4.services.text_chunker import (
    TextChunker,
    create_text_chunker,
)
from src.l4.storage.memory_store import (
    MemoryStore,
    MemoryCompressor,
    create_memory_store,
)
from src.l4.storage.cache_manager import (
    CacheManager,
    EmbeddingCache,
    SearchCache,
)
from src.l4.index.index_manager import (
    IndexManager,
    create_index_manager,
)

import logging
import hashlib

logger = logging.getLogger(__name__)


class MemoryKnowledge(MemoryInterface):
    """L4 implementation - Memory and knowledge management with RAG capabilities.

    This class integrates multiple components:
    - EmbeddingService: Converts text to vector embeddings
    - VectorStore: Stores and searches vector embeddings
    - TextChunker: Splits long texts into chunks
    - MemoryStore: Stores conversation history
    - CacheManager: Caches embeddings and search results
    - IndexManager: Manages vector indices

    Args:
        embedding_service: Embedding service instance or config dict
        vector_store: Vector store instance or config dict
        text_chunker: Text chunker instance or config dict
        memory_store: Memory store instance or config dict
        cache_manager: Cache manager instance or config dict
        index_manager: Index manager instance or config dict
        enable_caching: Whether to enable caching (default: True)

    Example:
        >>> # Default configuration
        >>> memory = MemoryKnowledge()
        >>>
        >>> # Custom configuration
        >>> memory = MemoryKnowledge(
        ...     embedding_service={"provider": "openai", "model": "text-embedding-3-small"},
        ...     vector_store={"store_type": "chroma", "collection_name": "my_docs"},
        ... )
    """

    DEFAULT_CACHE_SIZE = 1000
    DEFAULT_SEARCH_TOP_K = 5

    def __init__(
        self,
        embedding_service: Optional[Union[EmbeddingService, Dict]] = None,
        vector_store: Optional[Union[VectorStore, Dict]] = None,
        text_chunker: Optional[Union[TextChunker, Dict]] = None,
        memory_store: Optional[Union[MemoryStore, Dict]] = None,
        cache_manager: Optional[Union[CacheManager, Dict]] = None,
        index_manager: Optional[Union[IndexManager, Dict]] = None,
        enable_caching: bool = True,
    ):
        # Initialize embedding service
        if isinstance(embedding_service, EmbeddingService):
            self.embedding_service = embedding_service
        elif isinstance(embedding_service, dict):
            self.embedding_service = create_embedding_service(**embedding_service)
        else:
            # Default to mock for testing
            self.embedding_service = create_embedding_service("mock")

        # Initialize vector store
        if isinstance(vector_store, VectorStore):
            self.vector_store = vector_store
        elif isinstance(vector_store, dict):
            self.vector_store = create_vector_store(**vector_store)
        else:
            self.vector_store = create_vector_store("memory")

        # Initialize text chunker
        if isinstance(text_chunker, TextChunker):
            self.text_chunker = text_chunker
        elif isinstance(text_chunker, dict):
            self.text_chunker = create_text_chunker(**text_chunker)
        else:
            self.text_chunker = create_text_chunker("recursive")

        # Initialize memory store
        if isinstance(memory_store, MemoryStore):
            self.memory_store = memory_store
        elif isinstance(memory_store, dict):
            self.memory_store = create_memory_store(**memory_store)
        else:
            self.memory_store = create_memory_store("memory")

        # Initialize cache managers
        self.enable_caching = enable_caching
        if enable_caching:
            if isinstance(cache_manager, CacheManager):
                self.embedding_cache = EmbeddingCache()
                self.search_cache = SearchCache()
            elif isinstance(cache_manager, dict):
                self.embedding_cache = EmbeddingCache(**cache_manager)
                self.search_cache = SearchCache(**cache_manager)
            else:
                self.embedding_cache = EmbeddingCache()
                self.search_cache = SearchCache()
        else:
            self.embedding_cache = None
            self.search_cache = None

        # Initialize index manager
        if isinstance(index_manager, IndexManager):
            self.index_manager = index_manager
        elif isinstance(index_manager, dict):
            self.index_manager = create_index_manager(**index_manager)
        else:
            self.index_manager = None

        logger.info(
            f"Initialized MemoryKnowledge with: "
            f"embedding={type(self.embedding_service).__name__}, "
            f"vector_store={type(self.vector_store).__name__}, "
            f"caching={enable_caching}"
        )

    def search(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict] = None
    ) -> List[str]:
        """Search for relevant documents.

        Performs semantic search using vector similarity. Results are cached
        for improved performance on repeated queries.

        Args:
            query: Search query text
            top_k: Number of results to return (default: 5)
            filters: Optional metadata filters

        Returns:
            List of document content strings, ordered by relevance

        Raises:
            EmbeddingError: If embedding generation fails
            VectorStoreError: If vector search fails

        Example:
            >>> results = memory.search("machine learning", top_k=3)
            >>> for doc in results:
            ...     print(doc)
        """
        if not query or not query.strip():
            return []

        # Check search cache
        if self.enable_caching and self.search_cache:
            cached_results = self.search_cache.get_search_results(
                query, top_k, filters
            )
            if cached_results is not None:
                logger.debug(f"Search cache hit for query: {query[:50]}...")
                return cached_results

        try:
            # Generate query embedding
            query_embedding = self._get_embedding(query)

            # Search vector store
            results = self.vector_store.search(
                query_embedding=query_embedding,
                top_k=top_k,
                filters=filters,
            )

            # Extract content
            contents = [r["content"] for r in results]

            # Cache results
            if self.enable_caching and self.search_cache:
                self.search_cache.set_search_results(
                    query, top_k, filters, contents
                )

            return contents

        except EmbeddingError as e:
            logger.error(f"Embedding error during search: {e}")
            raise
        except VectorStoreError as e:
            logger.error(f"Vector store error during search: {e}")
            raise

    def search_with_scores(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict] = None
    ) -> List[Dict[str, Any]]:
        """Search for relevant documents with similarity scores.

        Similar to search() but returns full result objects including scores
        and metadata.

        Args:
            query: Search query text
            top_k: Number of results to return
            filters: Optional metadata filters

        Returns:
            List of result dictionaries with 'content', 'score', 'metadata', 'id'

        Example:
            >>> results = memory.search_with_scores("AI", top_k=2)
            >>> for r in results:
            ...     print(f"{r['score']:.2f}: {r['content'][:100]}")
        """
        if not query or not query.strip():
            return []

        try:
            query_embedding = self._get_embedding(query)

            results = self.vector_store.search(
                query_embedding=query_embedding,
                top_k=top_k,
                filters=filters,
            )

            return results

        except Exception as e:
            logger.error(f"Error during search_with_scores: {e}")
            raise

    def store(self, document: str, metadata: Dict[str, Any]) -> bool:
        """Store a document in the knowledge base.

        Documents are automatically chunked and embedded before storage.

        Args:
            document: Document content to store
            metadata: Document metadata (must include 'doc_id')

        Returns:
            True if successful

        Raises:
            ValueError: If document is empty or metadata is invalid
            EmbeddingError: If embedding generation fails

        Example:
            >>> memory.store(
            ...     "Python is a versatile programming language...",
            ...     {"doc_id": "py-intro", "source": "wikipedia"}
            ... )
            True
        """
        if not document or not document.strip():
            logger.warning("Attempted to store empty document")
            return False

        if not metadata or "doc_id" not in metadata:
            logger.warning("Document metadata missing 'doc_id'")
            return False

        try:
            # Chunk document
            chunks = self.text_chunker.split(document)
            logger.debug(f"Split document into {len(chunks)} chunks")

            # Generate embeddings
            embeddings = self.embedding_service.embed_batch(chunks)

            # Prepare documents for storage
            doc_id_base = metadata["doc_id"]
            documents = []

            for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                chunk_metadata = metadata.copy()
                chunk_metadata.update({
                    "chunk_index": i,
                    "chunk_count": len(chunks),
                })

                documents.append({
                    "id": f"{doc_id_base}_{i}",
                    "content": chunk,
                    "embedding": embedding,
                    "metadata": chunk_metadata,
                })

            # Store in vector store
            self.vector_store.add_documents(documents)
            logger.info(f"Stored document {doc_id_base} with {len(chunks)} chunks")

            return True

        except Exception as e:
            logger.error(f"Error storing document: {e}")
            raise

    def store_batch(
        self,
        documents: List[Dict[str, Any]]
    ) -> bool:
        """Store multiple documents efficiently.

        Args:
            documents: List of documents with 'content' and 'metadata'

        Returns:
            True if successful

        Example:
            >>> docs = [
            ...     {"content": "Doc 1", "metadata": {"doc_id": "d1"}},
            ...     {"content": "Doc 2", "metadata": {"doc_id": "d2"}},
            ... ]
            >>> memory.store_batch(docs)
            True
        """
        if not documents:
            return True

        try:
            all_chunks = []

            # Chunk all documents
            for doc in documents:
                content = doc.get("content", "")
                metadata = doc.get("metadata", {})
                doc_id = metadata.get("doc_id", "unknown")

                chunks = self.text_chunker.split(content)

                for i, chunk in enumerate(chunks):
                    chunk_metadata = metadata.copy()
                    chunk_metadata.update({
                        "chunk_index": i,
                        "chunk_count": len(chunks),
                    })

                    all_chunks.append({
                        "id": f"{doc_id}_{i}",
                        "content": chunk,
                        "metadata": chunk_metadata,
                    })

            # Generate embeddings in batch
            chunk_texts = [c["content"] for c in all_chunks]
            embeddings = self.embedding_service.embed_batch(chunk_texts)

            # Combine with documents
            for chunk, embedding in zip(all_chunks, embeddings):
                chunk["embedding"] = embedding

            # Store in vector store
            self.vector_store.add_documents(all_chunks)
            logger.info(f"Stored batch of {len(documents)} documents")

            return True

        except Exception as e:
            logger.error(f"Error storing batch: {e}")
            raise

    def delete(self, document_id: str) -> bool:
        """Delete a document and all its chunks.

        Args:
            document_id: Document ID (doc_id from metadata)

        Returns:
            True if successful
        """
        try:
            # Note: This deletes specific chunk IDs
            # In practice, you might need to track all chunk IDs for a document
            self.vector_store.delete([document_id])
            return True
        except Exception as e:
            logger.error(f"Error deleting document {document_id}: {e}")
            return False

    def store_conversation(
        self,
        session_id: str,
        messages: List[Dict[str, str]]
    ) -> bool:
        """Store conversation history with compression.

        Conversations are automatically compressed when they exceed
        the configured threshold to maintain efficiency.

        Args:
            session_id: Session identifier
            messages: List of messages in OpenAI format

        Returns:
            True if successful

        Example:
            >>> messages = [
            ...     {"role": "user", "content": "Hello!"},
            ...     {"role": "assistant", "content": "Hi there!"},
            ... ]
            >>> memory.store_conversation("session-123", messages)
            True
        """
        try:
            return self.memory_store.save_conversation(session_id, messages)
        except Exception as e:
            logger.error(f"Error storing conversation: {e}")
            return False

    def retrieve_history(
        self,
        session_id: str,
        limit: int = 10
    ) -> List[Dict[str, str]]:
        """Retrieve conversation history.

        Args:
            session_id: Session identifier
            limit: Maximum number of messages to return

        Returns:
            List of messages in OpenAI format

        Example:
            >>> history = memory.retrieve_history("session-123", limit=5)
            >>> for msg in history:
            ...     print(f"{msg['role']}: {msg['content']}")
        """
        try:
            return self.memory_store.load_conversation(session_id, limit)
        except Exception as e:
            logger.error(f"Error retrieving history: {e}")
            return []

    def get_full_history(self, session_id: str) -> List[Dict]:
        """Get full conversation history including compressed parts.

        Args:
            session_id: Session identifier

        Returns:
            Complete conversation history
        """
        if hasattr(self.memory_store, 'get_full_conversation'):
            return self.memory_store.get_full_conversation(session_id)
        return self.retrieve_history(session_id, limit=1000)

    def compress_session(self, session_id: str) -> bool:
        """Force compression of a session's history.

        Args:
            session_id: Session identifier

        Returns:
            True if compression was applied
        """
        if hasattr(self.memory_store, 'force_compress'):
            return self.memory_store.force_compress(session_id)
        return False

    def get_compression_stats(self, session_id: str) -> List[Dict]:
        """Get compression statistics for a session.

        Args:
            session_id: Session identifier

        Returns:
            List of compression statistics
        """
        if hasattr(self.memory_store, 'get_compression_stats'):
            return self.memory_store.get_compression_stats(session_id)
        return []

    def save_user_preference(
        self,
        user_id: str,
        key: str,
        value: Any
    ) -> bool:
        """Save a user preference.

        Args:
            user_id: User identifier
            key: Preference key
            value: Preference value

        Returns:
            True if successful
        """
        try:
            return self.memory_store.save_preference(user_id, key, value)
        except Exception as e:
            logger.error(f"Error saving preference: {e}")
            return False

    def load_user_preference(
        self,
        user_id: str,
        key: str,
        default: Any = None
    ) -> Any:
        """Load a user preference.

        Args:
            user_id: User identifier
            key: Preference key
            default: Default value if not found

        Returns:
            Preference value or default
        """
        try:
            return self.memory_store.load_preference(user_id, key, default)
        except Exception as e:
            logger.error(f"Error loading preference: {e}")
            return default

    def delete_session(self, session_id: str) -> bool:
        """Delete a session and all its data.

        Args:
            session_id: Session identifier

        Returns:
            True if successful
        """
        try:
            return self.memory_store.delete_session(session_id)
        except Exception as e:
            logger.error(f"Error deleting session: {e}")
            return False

    def list_sessions(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """List available sessions.

        Args:
            user_id: Optional user ID to filter by

        Returns:
            List of session information
        """
        try:
            return self.memory_store.list_sessions(user_id)
        except Exception as e:
            logger.error(f"Error listing sessions: {e}")
            return []

    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive statistics about the memory layer.

        Returns:
            Dictionary with various statistics
        """
        stats = {
            "vector_store": self.vector_store.get_collection_stats(),
        }

        if self.enable_caching and self.embedding_cache:
            stats["embedding_cache"] = self.embedding_cache.stats()

        if self.enable_caching and self.search_cache:
            stats["search_cache"] = self.search_cache.stats()

        return stats

    def clear_cache(self) -> bool:
        """Clear all caches.

        Returns:
            True if successful
        """
        if self.embedding_cache:
            self.embedding_cache.clear()
        if self.search_cache:
            self.search_cache.clear()
        return True

    def _get_embedding(self, text: str) -> List[float]:
        """Get embedding for text, using cache if available.

        Args:
            text: Input text

        Returns:
            Embedding vector
        """
        # Check embedding cache
        if self.enable_caching and self.embedding_cache:
            provider = getattr(self.embedding_service, 'model', 'unknown')
            model = getattr(self.embedding_service, 'model_name', provider)
            cached = self.embedding_cache.get_embedding(text, provider, model)

            if cached is not None:
                return cached

        # Generate embedding
        embedding = self.embedding_service.embed(text)

        # Cache embedding
        if self.enable_caching and self.embedding_cache:
            provider = getattr(self.embedding_service, 'model', 'unknown')
            model = getattr(self.embedding_service, 'model_name', provider)
            self.embedding_cache.set_embedding(text, provider, model, embedding)

        return embedding

    def _generate_doc_id(self, content: str, prefix: str = "doc") -> str:
        """Generate a deterministic document ID from content.

        Args:
            content: Document content
            prefix: ID prefix

        Returns:
            Unique document ID
        """
        hash_val = hashlib.md5(content.encode()).hexdigest()[:12]
        return f"{prefix}_{hash_val}"


# Convenience functions for quick usage
def create_memory_knowledge(
    provider: str = "mock",
    vector_store_type: str = "memory",
    **kwargs
) -> MemoryKnowledge:
    """Factory function to create MemoryKnowledge with common configurations.

    Args:
        provider: Embedding provider ('openai', 'sentence-transformers', 'mock')
        vector_store_type: Vector store type ('memory', 'chroma', 'faiss')
        **kwargs: Additional configuration options

    Returns:
        Configured MemoryKnowledge instance

    Example:
        >>> # Quick start with mock (for testing)
        >>> memory = create_memory_knowledge("mock")
        >>>
        >>> # Production setup with OpenAI and ChromaDB
        >>> memory = create_memory_knowledge(
        ...     "openai",
        ...     "chroma",
        ...     persist_directory="./chroma_data"
        ... )
    """
    embedding_config = {"provider": provider}
    if provider == "openai" and "model" in kwargs:
        embedding_config["model"] = kwargs.pop("model")

    vector_config = {"store_type": vector_store_type}
    if "persist_directory" in kwargs:
        vector_config["persist_directory"] = kwargs.pop("persist_directory")
    if "collection_name" in kwargs:
        vector_config["collection_name"] = kwargs.pop("collection_name")

    return MemoryKnowledge(
        embedding_service=embedding_config,
        vector_store=vector_config,
        **kwargs
    )

"""L4: Memory & Knowledge Layer

This module provides vector search, memory storage, and RAG capabilities
for the VClaw AI Agent system.

Package Structure:
    src/l4/
    ├── core/           # Core L4 implementation
    │   └── l4_memory.py    # Main MemoryKnowledge class
    ├── services/       # Service implementations
    │   ├── embedding.py    # Embedding services (OpenAI, Local, Mock)
    │   └── text_chunker.py # Text chunking strategies
    ├── storage/        # Storage implementations
    │   ├── vector_store.py # Vector databases (ChromaDB, FAISS, Memory)
    │   ├── memory_store.py # Conversation & preference storage
    │   └── cache_manager.py # LRU cache with TTL
    ├── index/          # Index management
    │   └── index_manager.py # Vector index lifecycle
    └── tests/          # Unit tests

Quick Start:
    >>> from src.l4 import MemoryKnowledge
    >>> memory = MemoryKnowledge()
    >>> memory.store("Python is a programming language", {"doc_id": "py-001"})
    >>> results = memory.search("programming languages")
    >>> print(results)

Production Configuration:
    >>> from src.l4 import MemoryKnowledge
    >>> memory = MemoryKnowledge(
    ...     embedding_service={"provider": "openai", "model": "text-embedding-3-small"},
    ...     vector_store={"store_type": "chroma", "collection_name": "docs"},
    ... )
"""

# Core class
from src.l4.core.l4_memory import MemoryKnowledge, create_memory_knowledge

# Services - Embedding
from src.l4.services.embedding import (
    EmbeddingService,
    OpenAIEmbeddingService,
    SentenceTransformerService,
    MockEmbeddingService,
    EmbeddingError,
    create_embedding_service,
)

# Services - Text Chunking
from src.l4.services.text_chunker import (
    TextChunker,
    RecursiveTextChunker,
    TokenTextChunker,
    MarkdownTextChunker,
    CharacterTextChunker,
    create_text_chunker,
)

# Storage - Vector Store
from src.l4.storage.vector_store import (
    VectorStore,
    MemoryVectorStore,
    ChromaVectorStore,
    FaissVectorStore,
    VectorStoreError,
    create_vector_store,
)

# Storage - Memory Store
from src.l4.storage.memory_store import (
    MemoryStore,
    InMemoryStore,
    FileMemoryStore,
    MemoryCompressor,
    create_memory_store,
)

# Storage - Cache Manager
from src.l4.storage.cache_manager import (
    CacheManager,
    EmbeddingCache,
    SearchCache,
)

# Index Management
from src.l4.index.index_manager import (
    IndexManager,
    ChromaIndexManager,
    MemoryIndexManager,
    create_index_manager,
)

__all__ = [
    # Core
    "MemoryKnowledge",
    "create_memory_knowledge",
    # Services - Embedding
    "EmbeddingService",
    "OpenAIEmbeddingService",
    "SentenceTransformerService",
    "MockEmbeddingService",
    "EmbeddingError",
    "create_embedding_service",
    # Services - Text Chunking
    "TextChunker",
    "RecursiveTextChunker",
    "TokenTextChunker",
    "MarkdownTextChunker",
    "CharacterTextChunker",
    "create_text_chunker",
    # Storage - Vector Store
    "VectorStore",
    "MemoryVectorStore",
    "ChromaVectorStore",
    "FaissVectorStore",
    "VectorStoreError",
    "create_vector_store",
    # Storage - Memory Store
    "MemoryStore",
    "InMemoryStore",
    "FileMemoryStore",
    "MemoryCompressor",
    "create_memory_store",
    # Storage - Cache
    "CacheManager",
    "EmbeddingCache",
    "SearchCache",
    # Index Management
    "IndexManager",
    "ChromaIndexManager",
    "MemoryIndexManager",
    "create_index_manager",
]

__version__ = "1.0.0"

"""L4 Memory & Knowledge Layer Configuration.

This module provides centralized configuration for the L4 layer,
reading from environment variables and .env file.

Usage:
    from src.l4.config.l4_config import get_l4_memory

    # Get configured L4 memory instance
    memory = get_l4_memory()

    # Or access configuration directly
    from src.l4.config.l4_config import L4_CONFIG
    embedding_config = L4_CONFIG["embedding"]
"""
import os
from typing import Dict, Any, Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv(override=True)


# =============================================================================
# L4 Configuration Dictionary
# =============================================================================

L4_CONFIG: Dict[str, Any] = {
    # -------------------------------------------------------------------------
    # Embedding Service Configuration
    # -------------------------------------------------------------------------
    "embedding": {
        "provider": os.getenv("L4_EMBEDDING_PROVIDER", "mock"),
        "model": os.getenv("L4_EMBEDDING_MODEL", "text-embedding-3-small"),
        "api_key": os.getenv("L4_EMBEDDING_API_KEY") or os.getenv("OPENAI_API_KEY"),
        "base_url": os.getenv("L4_EMBEDDING_BASE_URL") or os.getenv("OPENAI_BASE_URL"),
        # Sentence Transformers settings
        "model_name": os.getenv("L4_SENTENCE_TRANSFORMER_MODEL", "all-MiniLM-L6-v2"),
        "device": os.getenv("L4_SENTENCE_TRANSFORMER_DEVICE", "cpu"),
    },

    # -------------------------------------------------------------------------
    # Vector Store Configuration
    # -------------------------------------------------------------------------
    "vector_store": {
        "store_type": os.getenv("L4_VECTOR_STORE_TYPE", "memory"),
        # ChromaDB settings
        "collection_name": os.getenv("L4_CHROMA_COLLECTION_NAME", "vclaw_knowledge"),
        "persist_directory": os.getenv("L4_CHROMA_PERSIST_DIR", "./src/l4/data/chroma_db"),
        # FAISS settings
        "dimension": int(os.getenv("L4_FAISS_DIMENSION", "1536")),
        "index_type": os.getenv("L4_FAISS_INDEX_TYPE", "IndexFlatIP"),
    },

    # -------------------------------------------------------------------------
    # Text Chunker Configuration
    # -------------------------------------------------------------------------
    "text_chunker": {
        "chunker_type": os.getenv("L4_CHUNKER_TYPE", "recursive"),
        "chunk_size": int(os.getenv("L4_CHUNK_SIZE", "1000")),
        "chunk_overlap": int(os.getenv("L4_CHUNK_OVERLAP", "200")),
        # Token chunker settings
        "encoding_name": os.getenv("L4_TOKEN_ENCODING"),
        "language": "default",
    },

    # -------------------------------------------------------------------------
    # Memory Store Configuration
    # -------------------------------------------------------------------------
    "memory_store": {
        "store_type": os.getenv("L4_MEMORY_STORE_TYPE", "file"),
        "storage_dir": os.getenv("L4_MEMORY_STORAGE_DIR", "./src/l4/data/conversations"),
        # Compression settings
        "max_messages": int(os.getenv("L4_COMPRESSION_MAX_MESSAGES", "20")),
        "compression_threshold": int(os.getenv("L4_COMPRESSION_THRESHOLD", "10")),
    },

    # -------------------------------------------------------------------------
    # Cache Configuration
    # -------------------------------------------------------------------------
    "cache": {
        "enable": os.getenv("L4_CACHE_ENABLED", "true").lower() == "true",
        "max_size": int(os.getenv("L4_CACHE_MAX_SIZE", "1000")),
        "default_ttl": int(os.getenv("L4_CACHE_DEFAULT_TTL", "3600")),
    },

    # -------------------------------------------------------------------------
    # Index Manager Configuration
    # -------------------------------------------------------------------------
    "index_manager": {
        "manager_type": "chroma" if os.getenv("L4_VECTOR_STORE_TYPE") == "chroma" else "memory",
        "persist_directory": os.getenv("L4_CHROMA_PERSIST_DIR", "./src/l4/data/chroma_db"),
    },
}


# =============================================================================
# Helper Functions
# =============================================================================

def get_l4_memory(config: Optional[Dict[str, Any]] = None):
    """Create and configure L4 MemoryKnowledge instance.

    This is the main entry point for getting a configured L4 instance.
    It reads configuration from environment variables and creates the
    appropriate MemoryKnowledge instance.

    Args:
        config: Optional configuration override. If not provided, uses L4_CONFIG.

    Returns:
        MemoryKnowledge: Configured L4 memory instance.

    Example:
        >>> from config.l4_config import get_l4_memory
        >>> memory = get_l4_memory()
        >>> memory.store("Document content", {"doc_id": "doc1"})

        # With custom config
        >>> custom_config = {"embedding": {"provider": "mock"}}
        >>> memory = get_l4_memory(custom_config)
    """
    from src.l4 import MemoryKnowledge

    cfg = (config or L4_CONFIG).copy()

    # Clean up embedding config based on provider
    embedding_config = cfg["embedding"].copy()
    provider = embedding_config.get("provider", "mock")

    if provider == "mock":
        # Remove OpenAI-specific keys for mock provider
        embedding_config = {
            "provider": "mock",
            "dimension": embedding_config.get("dimension", 1536)
        }
    elif provider == "openai":
        # Remove sentence-transformers keys for OpenAI
        keys_to_remove = ["model_name", "device"]
        for key in keys_to_remove:
            embedding_config.pop(key, None)

    # Clean up memory_store config
    memory_store_config = cfg["memory_store"].copy()
    # Remove compression settings (they are used internally)
    keys_to_remove = ["max_messages", "compression_threshold"]
    for key in keys_to_remove:
        memory_store_config.pop(key, None)

    # Clean up text_chunker config based on chunker type
    text_chunker_config = cfg["text_chunker"].copy()
    chunker_type = text_chunker_config.get("chunker_type", "recursive")

    if chunker_type == "recursive" or chunker_type == "character" or chunker_type == "markdown":
        # Remove token-specific keys
        keys_to_remove = ["encoding_name", "language"]
        for key in keys_to_remove:
            text_chunker_config.pop(key, None)

    # Clean up vector_store config based on store type
    vector_store_config = cfg["vector_store"].copy()
    store_type = vector_store_config.get("store_type", "memory")

    if store_type == "chroma":
        # Remove FAISS-specific keys for Chroma
        keys_to_remove = ["index_type", "nlist"]
        for key in keys_to_remove:
            vector_store_config.pop(key, None)
    elif store_type == "memory":
        # Remove Chroma-specific keys for memory store
        keys_to_remove = ["collection_name", "persist_directory", "index_type", "nlist"]
        for key in keys_to_remove:
            vector_store_config.pop(key, None)

    return MemoryKnowledge(
        embedding_service=embedding_config,
        vector_store=vector_store_config,
        text_chunker=text_chunker_config,
        memory_store=memory_store_config,
        enable_caching=cfg["cache"]["enable"]
    )


def get_l4_memory_production():
    """Get L4 Memory configured for production (OpenAI + ChromaDB).

    This is a convenience function for the recommended production setup.

    Required environment variables:
        - OPENAI_API_KEY: Your OpenAI API key

    Optional environment variables:
        - L4_CHROMA_PERSIST_DIR: ChromaDB persistence directory (default: ./data/chroma_db)
        - L4_MEMORY_STORAGE_DIR: Conversation storage directory (default: ./data/conversations)

    Returns:
        MemoryKnowledge: Production-configured L4 instance

    Raises:
        ValueError: If OPENAI_API_KEY is not set
    """
    import os

    if not os.getenv("OPENAI_API_KEY"):
        raise ValueError(
            "OPENAI_API_KEY environment variable is required for production mode. "
            "Please set it in your .env file or environment."
        )

    # Ensure data directories exist
    os.makedirs("./data/chroma_db", exist_ok=True)
    os.makedirs("./data/conversations", exist_ok=True)

    config = {
        "embedding": {
            "provider": "openai",
            "model": "text-embedding-3-small",
            "api_key": os.getenv("OPENAI_API_KEY"),
            "base_url": os.getenv("OPENAI_BASE_URL"),
        },
        "vector_store": {
            "store_type": "chroma",
            "collection_name": "vclaw_knowledge",
            "persist_directory": "./data/chroma_db",
        },
        "text_chunker": {
            "chunker_type": "recursive",
            "chunk_size": 1000,
            "chunk_overlap": 200,
        },
        "memory_store": {
            "store_type": "file",
            "storage_dir": "./data/conversations",
        },
        "cache": {
            "enable": True,
            "max_size": 1000,
            "default_ttl": 3600,
        }
    }

    return get_l4_memory(config)


def get_l4_memory_development():
    """Get L4 Memory configured for development (Mock + Memory).

    This configuration uses mock embedding and in-memory storage,
    requiring no external dependencies or API keys.

    Returns:
        MemoryKnowledge: Development-configured L4 instance
    """
    config = {
        "embedding": {
            "provider": "mock",
            "dimension": 1536,
        },
        "vector_store": {
            "store_type": "memory",
        },
        "text_chunker": {
            "chunker_type": "recursive",
            "chunk_size": 1000,
            "chunk_overlap": 200,
        },
        "memory_store": {
            "store_type": "memory",
        },
        "cache": {
            "enable": True,
            "max_size": 100,
            "default_ttl": 300,
        }
    }

    return get_l4_memory(config)


def validate_l4_config() -> Dict[str, list]:
    """Validate L4 configuration and return any issues.

    Returns:
        Dict with 'errors' and 'warnings' lists

    Example:
        >>> issues = validate_l4_config()
        >>> if issues['errors']:
        ...     print("Configuration errors:", issues['errors'])
    """
    import os

    errors = []
    warnings = []

    # Check embedding provider
    embedding_provider = os.getenv("L4_EMBEDDING_PROVIDER", "mock")

    if embedding_provider == "openai":
        if not os.getenv("OPENAI_API_KEY") and not os.getenv("L4_EMBEDDING_API_KEY"):
            errors.append("OPENAI_API_KEY is required when using OpenAI embedding provider")

    elif embedding_provider == "sentence-transformers":
        try:
            import sentence_transformers
        except ImportError:
            errors.append("sentence-transformers package is required for local embedding")

    # Check vector store
    vector_store = os.getenv("L4_VECTOR_STORE_TYPE", "memory")

    if vector_store == "chroma":
        try:
            import chromadb
        except ImportError:
            errors.append("chromadb package is required for ChromaDB vector store")

        persist_dir = os.getenv("L4_CHROMA_PERSIST_DIR", "./data/chroma_db")
        if not os.path.exists(persist_dir):
            warnings.append(f"ChromaDB persistence directory does not exist: {persist_dir}")

    elif vector_store == "faiss":
        try:
            import faiss
        except ImportError:
            errors.append("faiss-cpu or faiss-gpu package is required for FAISS vector store")

    # Check memory store
    memory_store = os.getenv("L4_MEMORY_STORE_TYPE", "memory")

    if memory_store == "file":
        storage_dir = os.getenv("L4_MEMORY_STORAGE_DIR", "./data/conversations")
        if not os.path.exists(storage_dir):
            warnings.append(f"Memory storage directory does not exist: {storage_dir}")

    return {"errors": errors, "warnings": warnings}


# =============================================================================
# Auto-initialization (optional)
# =============================================================================

def init_l4_data_directories():
    """Create necessary data directories for L4.

    This function creates the following directories if they don't exist:
        - ./src/l4/data/chroma_db (ChromaDB persistence)
        - ./src/l4/data/conversations (Conversation history)
    """
    import os

    directories = [
        "./src/l4/data/chroma_db",
        "./src/l4/data/conversations",
    ]

    for directory in directories:
        os.makedirs(directory, exist_ok=True)
        print(f"[OK] Ensured directory exists: {directory}")


if __name__ == "__main__":
    # Run validation when executed directly
    print("Validating L4 configuration...")

    issues = validate_l4_config()

    if issues["errors"]:
        print("\n[ERROR] Errors:")
        for error in issues["errors"]:
            print(f"  - {error}")

    if issues["warnings"]:
        print("\n[WARN] Warnings:")
        for warning in issues["warnings"]:
            print(f"  - {warning}")

    if not issues["errors"] and not issues["warnings"]:
        print("\n[OK] Configuration is valid!")

    print("\nCreating data directories...")
    init_l4_data_directories()

    print("\nConfiguration:")
    import json
    print(json.dumps(L4_CONFIG, indent=2, default=str))

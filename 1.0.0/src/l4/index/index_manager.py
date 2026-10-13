"""L4: Index Manager - Vector index lifecycle management."""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class IndexManager(ABC):
    """Abstract base class for index managers."""

    @abstractmethod
    def create_index(
        self,
        name: str,
        dimension: int,
        **kwargs
    ) -> bool:
        """Create a new vector index.

        Args:
            name: Index name
            dimension: Embedding dimension
            **kwargs: Additional index-specific options

        Returns:
            True if successful
        """
        pass

    @abstractmethod
    def delete_index(self, name: str) -> bool:
        """Delete a vector index.

        Args:
            name: Index name

        Returns:
            True if successful
        """
        pass

    @abstractmethod
    def list_indices(self) -> List[Dict[str, Any]]:
        """List all indices.

        Returns:
            List of index information dictionaries
        """
        pass

    @abstractmethod
    def get_index_stats(self, name: str) -> Dict[str, Any]:
        """Get statistics for an index.

        Args:
            name: Index name

        Returns:
            Index statistics
        """
        pass

    @abstractmethod
    def optimize_index(self, name: str) -> bool:
        """Optimize an index for better performance.

        Args:
            name: Index name

        Returns:
            True if successful
        """
        pass

    @abstractmethod
    def index_exists(self, name: str) -> bool:
        """Check if an index exists.

        Args:
            name: Index name

        Returns:
            True if index exists
        """
        pass


class ChromaIndexManager(IndexManager):
    """Index manager for ChromaDB."""

    def __init__(self, client=None, persist_directory: Optional[str] = None):
        """Initialize Chroma index manager.

        Args:
            client: Existing ChromaDB client (optional)
            persist_directory: Directory for persistent storage
        """
        if client:
            self.client = client
        else:
            try:
                import chromadb
                from chromadb.config import Settings
            except ImportError:
                raise ImportError(
                    "chromadb package is required. "
                    "Install with: pip install chromadb"
                )

            if persist_directory:
                self.client = chromadb.Client(
                    Settings(
                        persist_directory=persist_directory,
                        anonymized_telemetry=False,
                    )
                )
            else:
                self.client = chromadb.Client(
                    Settings(anonymized_telemetry=False)
                )

    def create_index(
        self,
        name: str,
        dimension: int,
        distance_metric: str = "cosine",
        **kwargs
    ) -> bool:
        """Create a new ChromaDB collection."""
        try:
            self.client.create_collection(
                name=name,
                metadata={
                    "dimension": dimension,
                    "distance_metric": distance_metric,
                    "created_at": datetime.now().isoformat(),
                    **kwargs
                }
            )
            logger.info(f"Created ChromaDB collection: {name}")
            return True
        except Exception as e:
            logger.error(f"Failed to create collection {name}: {e}")
            return False

    def delete_index(self, name: str) -> bool:
        """Delete a ChromaDB collection."""
        try:
            self.client.delete_collection(name=name)
            logger.info(f"Deleted ChromaDB collection: {name}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete collection {name}: {e}")
            return False

    def list_indices(self) -> List[Dict[str, Any]]:
        """List all ChromaDB collections."""
        try:
            collections = self.client.list_collections()
            result = []

            for collection in collections:
                try:
                    # Try to get collection info
                    if hasattr(collection, 'name'):
                        coll_name = collection.name
                    else:
                        coll_name = str(collection)

                    # Get collection to access metadata
                    coll = self.client.get_collection(coll_name)
                    metadata = coll.metadata or {}

                    result.append({
                        "name": coll_name,
                        "dimension": metadata.get("dimension"),
                        "distance_metric": metadata.get("distance_metric", "cosine"),
                        "created_at": metadata.get("created_at"),
                        "document_count": coll.count(),
                    })
                except Exception as e:
                    logger.warning(f"Failed to get info for collection: {e}")
                    continue

            return result
        except Exception as e:
            logger.error(f"Failed to list collections: {e}")
            return []

    def get_index_stats(self, name: str) -> Dict[str, Any]:
        """Get statistics for a ChromaDB collection."""
        try:
            collection = self.client.get_collection(name)
            metadata = collection.metadata or {}

            return {
                "name": name,
                "exists": True,
                "document_count": collection.count(),
                "dimension": metadata.get("dimension"),
                "distance_metric": metadata.get("distance_metric", "cosine"),
                "created_at": metadata.get("created_at"),
            }
        except Exception as e:
            logger.error(f"Failed to get stats for collection {name}: {e}")
            return {
                "name": name,
                "exists": False,
                "error": str(e),
            }

    def optimize_index(self, name: str) -> bool:
        """Optimize a ChromaDB collection.

        Note: ChromaDB handles optimization automatically in most cases.
        This method persists data if using persistent client.
        """
        try:
            # For persistent clients, this ensures data is written to disk
            if hasattr(self.client, 'persist'):
                self.client.persist()
                logger.info(f"Persisted ChromaDB collection: {name}")
            return True
        except Exception as e:
            logger.error(f"Failed to optimize collection {name}: {e}")
            return False

    def index_exists(self, name: str) -> bool:
        """Check if a ChromaDB collection exists."""
        try:
            collections = self.client.list_collections()
            collection_names = []

            for coll in collections:
                if hasattr(coll, 'name'):
                    collection_names.append(coll.name)
                else:
                    collection_names.append(str(coll))

            return name in collection_names
        except Exception as e:
            logger.error(f"Failed to check if collection exists: {e}")
            return False


class MemoryIndexManager(IndexManager):
    """In-memory index manager for testing."""

    def __init__(self):
        self.indices: Dict[str, Dict[str, Any]] = {}

    def create_index(
        self,
        name: str,
        dimension: int,
        **kwargs
    ) -> bool:
        """Create a new in-memory index."""
        if name in self.indices:
            logger.warning(f"Index {name} already exists")
            return False

        self.indices[name] = {
            "name": name,
            "dimension": dimension,
            "created_at": datetime.now().isoformat(),
            "document_count": 0,
            "metadata": kwargs,
        }
        logger.info(f"Created in-memory index: {name}")
        return True

    def delete_index(self, name: str) -> bool:
        """Delete an in-memory index."""
        if name not in self.indices:
            return False

        del self.indices[name]
        logger.info(f"Deleted in-memory index: {name}")
        return True

    def list_indices(self) -> List[Dict[str, Any]]:
        """List all in-memory indices."""
        return [
            {
                "name": idx["name"],
                "dimension": idx["dimension"],
                "created_at": idx["created_at"],
                "document_count": idx["document_count"],
            }
            for idx in self.indices.values()
        ]

    def get_index_stats(self, name: str) -> Dict[str, Any]:
        """Get statistics for an in-memory index."""
        if name not in self.indices:
            return {
                "name": name,
                "exists": False,
            }

        idx = self.indices[name]
        return {
            "name": name,
            "exists": True,
            "dimension": idx["dimension"],
            "document_count": idx["document_count"],
            "created_at": idx["created_at"],
            "metadata": idx["metadata"],
        }

    def optimize_index(self, name: str) -> bool:
        """Optimize an in-memory index (no-op)."""
        return name in self.indices

    def index_exists(self, name: str) -> bool:
        """Check if an in-memory index exists."""
        return name in self.indices

    def update_document_count(self, name: str, count: int):
        """Update document count for an index."""
        if name in self.indices:
            self.indices[name]["document_count"] = count


def create_index_manager(
    manager_type: str = "memory",
    **kwargs
) -> IndexManager:
    """Factory function to create index manager.

    Args:
        manager_type: Type of manager ('memory', 'chroma')
        **kwargs: Manager-specific arguments

    Returns:
        IndexManager instance

    Raises:
        ValueError: If manager_type is not supported
    """
    manager_type = manager_type.lower()

    if manager_type == "memory":
        return MemoryIndexManager()
    elif manager_type == "chroma":
        return ChromaIndexManager(**kwargs)
    else:
        raise ValueError(
            f"Unsupported index manager type: {manager_type}. "
            f"Supported: memory, chroma"
        )

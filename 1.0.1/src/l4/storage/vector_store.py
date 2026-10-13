"""L4: Vector Store - Vector database abstraction and implementations."""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Tuple
import logging
import numpy as np

logger = logging.getLogger(__name__)


class VectorStore(ABC):
    """Abstract base class for vector stores."""

    @abstractmethod
    def add_documents(
        self,
        documents: List[Dict[str, Any]]
    ) -> bool:
        """Add documents to the vector store.

        Args:
            documents: List of documents with 'id', 'content', 'embedding', 'metadata'

        Returns:
            True if successful
        """
        pass

    @abstractmethod
    def search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Search for similar documents.

        Args:
            query_embedding: Query vector
            top_k: Number of results to return
            filters: Optional metadata filters

        Returns:
            List of documents with 'content', 'score', 'metadata'
        """
        pass

    @abstractmethod
    def delete(
        self,
        document_ids: List[str]
    ) -> bool:
        """Delete documents by ID.

        Args:
            document_ids: List of document IDs to delete

        Returns:
            True if successful
        """
        pass

    @abstractmethod
    def get_collection_stats(self) -> Dict[str, Any]:
        """Get statistics about the collection.

        Returns:
            Dictionary with collection statistics
        """
        pass

    @staticmethod
    def cosine_similarity(a: List[float], b: List[float]) -> float:
        """Calculate cosine similarity between two vectors.

        Args:
            a: First vector
            b: Second vector

        Returns:
            Cosine similarity score (0 to 1)
        """
        a_array = np.array(a)
        b_array = np.array(b)

        norm_a = np.linalg.norm(a_array)
        norm_b = np.linalg.norm(b_array)

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return float(np.dot(a_array, b_array) / (norm_a * norm_b))


class MemoryVectorStore(VectorStore):
    """In-memory vector store for testing and small datasets."""

    def __init__(self, dimension: Optional[int] = None):
        """Initialize memory vector store.

        Args:
            dimension: Expected embedding dimension (optional, for validation)
        """
        self.documents: Dict[str, Dict[str, Any]] = {}  # id -> {content, embedding, metadata}
        self.dimension = dimension

    def add_documents(self, documents: List[Dict[str, Any]]) -> bool:
        """Add documents to memory store."""
        for doc in documents:
            doc_id = doc.get("id")
            if not doc_id:
                logger.warning("Document missing 'id', skipping")
                continue

            embedding = doc.get("embedding", [])

            # Validate dimension
            if self.dimension and embedding:
                if len(embedding) != self.dimension:
                    logger.warning(
                        f"Document {doc_id} has wrong dimension: "
                        f"{len(embedding)} vs {self.dimension}"
                    )
                    continue

            self.documents[doc_id] = {
                "content": doc.get("content", ""),
                "embedding": embedding,
                "metadata": doc.get("metadata", {}),
            }

        return True

    def search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Search for similar documents using cosine similarity."""
        if not self.documents:
            return []

        # Validate query dimension
        if self.dimension and len(query_embedding) != self.dimension:
            logger.warning(
                f"Query has wrong dimension: {len(query_embedding)} vs {self.dimension}"
            )
            return []

        results = []

        for doc_id, doc in self.documents.items():
            # Apply metadata filters
            if filters and not self._matches_filters(doc.get("metadata", {}), filters):
                continue

            # Calculate similarity
            doc_embedding = doc.get("embedding", [])
            if doc_embedding:
                score = self.cosine_similarity(query_embedding, doc_embedding)
            else:
                score = 0.0

            results.append({
                "id": doc_id,
                "content": doc["content"],
                "score": score,
                "metadata": doc.get("metadata", {}),
            })

        # Sort by score (descending) and return top_k
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    def delete(self, document_ids: List[str]) -> bool:
        """Delete documents by ID."""
        for doc_id in document_ids:
            if doc_id in self.documents:
                del self.documents[doc_id]
            else:
                logger.warning(f"Document {doc_id} not found for deletion")

        return True

    def get_collection_stats(self) -> Dict[str, Any]:
        """Get collection statistics."""
        return {
            "document_count": len(self.documents),
            "dimension": self.dimension,
            "store_type": "memory",
        }

    def _matches_filters(
        self,
        metadata: Dict[str, Any],
        filters: Dict[str, Any]
    ) -> bool:
        """Check if metadata matches filters.

        Supports:
        - Exact match: {"key": "value"}
        - Range: {"key": {"gte": 1, "lte": 10}}
        - List membership: {"key": {"in": ["a", "b"]}}
        """
        for key, value in filters.items():
            if key not in metadata:
                return False

            meta_value = metadata[key]

            # Range filter
            if isinstance(value, dict):
                if "gte" in value and meta_value < value["gte"]:
                    return False
                if "gt" in value and meta_value <= value["gt"]:
                    return False
                if "lte" in value and meta_value > value["lte"]:
                    return False
                if "lt" in value and meta_value >= value["lt"]:
                    return False
                if "in" in value and meta_value not in value["in"]:
                    return False
            # Exact match
            elif meta_value != value:
                return False

        return True


class ChromaVectorStore(VectorStore):
    """ChromaDB vector store implementation."""

    def __init__(
        self,
        collection_name: str = "default",
        persist_directory: Optional[str] = None,
        dimension: Optional[int] = None,
        distance_metric: str = "cosine",
    ):
        """Initialize ChromaDB vector store.

        Args:
            collection_name: Name of the collection
            persist_directory: Directory to persist data (None for in-memory)
            dimension: Embedding dimension
            distance_metric: Distance metric (cosine, l2, ip)
        """
        try:
            import chromadb
            from chromadb.config import Settings
        except ImportError:
            raise ImportError(
                "chromadb package is required for ChromaVectorStore. "
                "Install with: pip install chromadb"
            )

        self.collection_name = collection_name
        self.dimension = dimension
        self.distance_metric = distance_metric

        # Initialize ChromaDB client
        if persist_directory:
            self.client = chromadb.Client(
                Settings(
                    persist_directory=persist_directory,
                    anonymized_telemetry=False,
                )
            )
        else:
            self.client = chromadb.Client(
                Settings(
                    anonymized_telemetry=False,
                )
            )

        # Get or create collection
        try:
            self.collection = self.client.get_or_create_collection(
                name=collection_name,
                metadata={
                    "dimension": str(dimension) if dimension else "",
                    "distance_metric": distance_metric,
                }
            )
            logger.info(f"Initialized ChromaVectorStore with collection: {collection_name}")
        except Exception as e:
            logger.error(f"Failed to create ChromaDB collection: {e}")
            raise VectorStoreError(f"Failed to initialize ChromaDB: {e}") from e

    def add_documents(self, documents: List[Dict[str, Any]]) -> bool:
        """Add documents to ChromaDB."""
        if not documents:
            return True

        ids = []
        embeddings = []
        metadatas = []
        contents = []

        for doc in documents:
            doc_id = doc.get("id")
            if not doc_id:
                logger.warning("Document missing 'id', skipping")
                continue

            ids.append(doc_id)
            embeddings.append(doc.get("embedding", []))
            metadatas.append(doc.get("metadata", {}))
            contents.append(doc.get("content", ""))

        try:
            self.collection.add(
                ids=ids,
                embeddings=embeddings,
                metadatas=metadatas,
                documents=contents,
            )
            return True
        except Exception as e:
            logger.error(f"Failed to add documents to ChromaDB: {e}")
            raise VectorStoreError(f"Failed to add documents: {e}") from e

    def search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Search for similar documents in ChromaDB."""
        try:
            # Convert filters to ChromaDB format
            where_clause = self._convert_filters(filters) if filters else None

            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                where=where_clause,
                include=["documents", "metadatas", "distances"],
            )

            # Format results
            formatted_results = []
            if results["ids"] and results["ids"][0]:
                for i, doc_id in enumerate(results["ids"][0]):
                    # Convert distance to similarity (Chroma returns distance)
                    distance = results["distances"][0][i]
                    if self.distance_metric == "cosine":
                        # Cosine distance to similarity: 1 - distance
                        score = 1.0 - distance
                    elif self.distance_metric == "l2":
                        # L2 distance to similarity (normalized)
                        score = 1.0 / (1.0 + distance)
                    else:
                        score = 1.0 - distance

                    formatted_results.append({
                        "id": doc_id,
                        "content": results["documents"][0][i] if results["documents"] else "",
                        "score": max(0.0, min(1.0, score)),
                        "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                    })

            return formatted_results

        except Exception as e:
            logger.error(f"Failed to search ChromaDB: {e}")
            raise VectorStoreError(f"Failed to search: {e}") from e

    def delete(self, document_ids: List[str]) -> bool:
        """Delete documents from ChromaDB."""
        try:
            self.collection.delete(ids=document_ids)
            return True
        except Exception as e:
            logger.error(f"Failed to delete documents from ChromaDB: {e}")
            raise VectorStoreError(f"Failed to delete documents: {e}") from e

    def get_collection_stats(self) -> Dict[str, Any]:
        """Get collection statistics."""
        try:
            count = self.collection.count()
            return {
                "document_count": count,
                "collection_name": self.collection_name,
                "dimension": self.dimension,
                "distance_metric": self.distance_metric,
                "store_type": "chroma",
            }
        except Exception as e:
            logger.error(f"Failed to get ChromaDB stats: {e}")
            return {
                "document_count": 0,
                "error": str(e),
            }

    def _convert_filters(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Convert generic filters to ChromaDB where clause format.

        ChromaDB supports:
        - {"key": "value"} - exact match
        - {"key": {"$gt": 1, "$lt": 10}} - range
        - {"$and": [...], "$or": [...]} - logical operators
        """
        chroma_filters = {}

        for key, value in filters.items():
            if isinstance(value, dict):
                # Range or list filter
                chroma_value = {}
                if "gte" in value:
                    chroma_value["$gte"] = value["gte"]
                if "gt" in value:
                    chroma_value["$gt"] = value["gt"]
                if "lte" in value:
                    chroma_value["$lte"] = value["lte"]
                if "lt" in value:
                    chroma_value["$lt"] = value["lt"]
                if "in" in value:
                    chroma_value["$in"] = value["in"]

                if chroma_value:
                    chroma_filters[key] = chroma_value
            else:
                # Exact match
                chroma_filters[key] = value

        return chroma_filters


class FaissVectorStore(VectorStore):
    """FAISS vector store for high-performance local search."""

    def __init__(
        self,
        dimension: int,
        index_type: str = "IndexFlatIP",  # Inner product (for normalized vectors = cosine)
        nlist: int = 100,  # For IVF indexes
    ):
        """Initialize FAISS vector store.

        Args:
            dimension: Embedding dimension (required)
            index_type: FAISS index type
            nlist: Number of clusters for IVF indexes
        """
        try:
            import faiss
        except ImportError:
            raise ImportError(
                "faiss-cpu or faiss-gpu package is required for FaissVectorStore. "
                "Install with: pip install faiss-cpu"
            )

        if not dimension:
            raise ValueError("dimension is required for FaissVectorStore")

        self.dimension = dimension
        self.index_type = index_type
        self.nlist = nlist
        self.faiss = faiss

        # Initialize index
        self._init_index()

        # Document storage (FAISS only stores vectors)
        self.documents: Dict[str, Dict[str, Any]] = {}
        self.id_to_index: Dict[str, int] = {}
        self.index_to_id: Dict[int, str] = {}
        self.current_index = 0

        logger.info(f"Initialized FaissVectorStore with index type: {index_type}")

    def _init_index(self):
        """Initialize FAISS index."""
        if self.index_type == "IndexFlatIP":
            self.index = self.faiss.IndexFlatIP(self.dimension)
        elif self.index_type == "IndexFlatL2":
            self.index = self.faiss.IndexFlatL2(self.dimension)
        elif self.index_type == "IndexIVFFlat":
            quantizer = self.faiss.IndexFlatIP(self.dimension)
            self.index = self.faiss.IndexIVFFlat(
                quantizer, self.dimension, self.nlist
            )
            self.index_is_trained = False
        else:
            raise ValueError(f"Unsupported index type: {self.index_type}")

        if self.index_type != "IndexIVFFlat":
            self.index_is_trained = True

    def add_documents(self, documents: List[Dict[str, Any]]) -> bool:
        """Add documents to FAISS index."""
        if not documents:
            return True

        embeddings = []
        valid_ids = []

        for doc in documents:
            doc_id = doc.get("id")
            embedding = doc.get("embedding", [])

            if not doc_id:
                logger.warning("Document missing 'id', skipping")
                continue

            if len(embedding) != self.dimension:
                logger.warning(
                    f"Document {doc_id} has wrong dimension, skipping"
                )
                continue

            embeddings.append(embedding)
            valid_ids.append(doc_id)

            # Store document metadata
            self.documents[doc_id] = {
                "content": doc.get("content", ""),
                "metadata": doc.get("metadata", {}),
            }

        if not embeddings:
            return True

        # Convert to numpy array
        embedding_array = np.array(embeddings, dtype=np.float32)

        # Normalize for cosine similarity (if using IndexFlatIP)
        if self.index_type == "IndexFlatIP":
            self.faiss.normalize_L2(embedding_array)

        # Train index if needed (for IVF)
        if not self.index_is_trained:
            self.index.train(embedding_array)
            self.index_is_trained = True

        # Add to index
        self.index.add(embedding_array)

        # Update ID mappings
        for i, doc_id in enumerate(valid_ids):
            self.id_to_index[doc_id] = self.current_index + i
            self.index_to_id[self.current_index + i] = doc_id

        self.current_index += len(valid_ids)

        return True

    def search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Search for similar documents in FAISS."""
        if self.current_index == 0:
            return []

        # Convert query to numpy array
        query_array = np.array([query_embedding], dtype=np.float32)

        # Normalize for cosine similarity
        if self.index_type == "IndexFlatIP":
            self.faiss.normalize_L2(query_array)

        # Search
        distances, indices = self.index.search(query_array, top_k)

        # Format results
        results = []
        for i, idx in enumerate(indices[0]):
            if idx == -1:  # FAISS returns -1 for empty results
                continue

            doc_id = self.index_to_id.get(int(idx))
            if not doc_id:
                continue

            doc = self.documents.get(doc_id, {})

            # Apply filters
            if filters and not self._matches_filters(doc.get("metadata", {}), filters):
                continue

            # Convert distance to score
            if self.index_type in ("IndexFlatIP", "IndexIVFFlat"):
                # Inner product (higher is better for normalized vectors)
                score = float(distances[0][i])
            else:
                # L2 distance (lower is better)
                score = 1.0 / (1.0 + float(distances[0][i]))

            results.append({
                "id": doc_id,
                "content": doc.get("content", ""),
                "score": max(0.0, min(1.0, score)),
                "metadata": doc.get("metadata", {}),
            })

        return results

    def delete(self, document_ids: List[str]) -> bool:
        """Delete documents from FAISS index.

        Note: FAISS doesn't support direct deletion. We mark as deleted
        and rebuild index if needed.
        """
        for doc_id in document_ids:
            if doc_id in self.documents:
                del self.documents[doc_id]
                if doc_id in self.id_to_index:
                    idx = self.id_to_index[doc_id]
                    del self.id_to_index[doc_id]
                    if idx in self.index_to_id:
                        del self.index_to_id[idx]
            else:
                logger.warning(f"Document {doc_id} not found for deletion")

        # Note: FAISS doesn't support direct deletion
        # In production, you might want to rebuild the index periodically
        return True

    def get_collection_stats(self) -> Dict[str, Any]:
        """Get collection statistics."""
        return {
            "document_count": len(self.documents),
            "index_count": self.current_index,
            "dimension": self.dimension,
            "index_type": self.index_type,
            "store_type": "faiss",
        }

    def _matches_filters(
        self,
        metadata: Dict[str, Any],
        filters: Dict[str, Any]
    ) -> bool:
        """Check if metadata matches filters."""
        for key, value in filters.items():
            if key not in metadata:
                return False

            meta_value = metadata[key]

            if isinstance(value, dict):
                if "gte" in value and meta_value < value["gte"]:
                    return False
                if "gt" in value and meta_value <= value["gt"]:
                    return False
                if "lte" in value and meta_value > value["lte"]:
                    return False
                if "lt" in value and meta_value >= value["lt"]:
                    return False
                if "in" in value and meta_value not in value["in"]:
                    return False
            elif meta_value != value:
                return False

        return True


class PineconeVectorStore(VectorStore):
    """Pinecone vector store implementation (stub - not yet implemented)."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        environment: Optional[str] = None,
        index_name: str = "default",
        dimension: Optional[int] = None,
    ):
        """Initialize Pinecone vector store.

        Args:
            api_key: Pinecone API key
            environment: Pinecone environment
            index_name: Name of the Pinecone index
            dimension: Embedding dimension
        """
        raise NotImplementedError(
            "PineconeVectorStore is not yet implemented. "
            "Planned for future release with Pinecone cloud vector database support."
        )

    def add_documents(self, documents: List[Dict[str, Any]]) -> bool:
        """Add documents to Pinecone (not implemented)."""
        raise NotImplementedError("PineconeVectorStore.add_documents is not implemented")

    def search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Search Pinecone (not implemented)."""
        raise NotImplementedError("PineconeVectorStore.search is not implemented")

    def delete(self, document_ids: List[str]) -> bool:
        """Delete documents from Pinecone (not implemented)."""
        raise NotImplementedError("PineconeVectorStore.delete is not implemented")

    def get_collection_stats(self) -> Dict[str, Any]:
        """Get Pinecone collection statistics (not implemented)."""
        raise NotImplementedError("PineconeVectorStore.get_collection_stats is not implemented")


class VectorStoreError(Exception):
    """Exception raised for vector store errors."""
    pass


def create_vector_store(
    store_type: str = "memory",
    **kwargs
) -> VectorStore:
    """Factory function to create vector store.

    Args:
        store_type: Type of store ('memory', 'chroma', 'faiss', 'pinecone')
        **kwargs: Store-specific arguments

    Returns:
        VectorStore instance

    Raises:
        ValueError: If store_type is not supported
    """
    store_type = store_type.lower()

    if store_type == "memory":
        return MemoryVectorStore(**kwargs)
    elif store_type == "chroma":
        return ChromaVectorStore(**kwargs)
    elif store_type == "faiss":
        return FaissVectorStore(**kwargs)
    elif store_type == "pinecone":
        return PineconeVectorStore(**kwargs)
    else:
        raise ValueError(
            f"Unsupported vector store type: {store_type}. "
            f"Supported: memory, chroma, faiss, pinecone"
        )

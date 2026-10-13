"""L4: Cache Manager - LRU cache with TTL support."""
from collections import OrderedDict
from typing import Any, Optional, Dict, Callable
from datetime import datetime, timedelta
import threading
import logging

logger = logging.getLogger(__name__)


class CacheEntry:
    """Cache entry with TTL support."""

    def __init__(self, value: Any, ttl_seconds: Optional[int] = None):
        self.value = value
        self.created_at = datetime.now()
        self.ttl_seconds = ttl_seconds
        self.access_count = 1
        self.last_accessed = datetime.now()

    def is_expired(self) -> bool:
        """Check if cache entry has expired."""
        if self.ttl_seconds is None:
            return False
        elapsed = (datetime.now() - self.created_at).total_seconds()
        return elapsed > self.ttl_seconds

    def touch(self):
        """Update access metadata."""
        self.access_count += 1
        self.last_accessed = datetime.now()


class CacheManager:
    """LRU Cache manager with TTL support."""

    def __init__(
        self,
        max_size: int = 1000,
        default_ttl: Optional[int] = 3600,  # 1 hour
        cleanup_interval: int = 300,  # 5 minutes
    ):
        """Initialize cache manager.

        Args:
            max_size: Maximum number of items in cache
            default_ttl: Default TTL in seconds (None for no expiration)
            cleanup_interval: Interval for background cleanup (if implemented)
        """
        self.max_size = max_size
        self.default_ttl = default_ttl
        self.cleanup_interval = cleanup_interval

        # Use OrderedDict for LRU (most recent at end)
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = threading.RLock()

        # Statistics
        self._hits = 0
        self._misses = 0
        self._evictions = 0

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found/expired
        """
        with self._lock:
            entry = self._cache.get(key)

            if entry is None:
                self._misses += 1
                return None

            if entry.is_expired():
                # Remove expired entry
                del self._cache[key]
                self._misses += 1
                return None

            # Update LRU order - move to end
            self._cache.move_to_end(key)
            entry.touch()

            self._hits += 1
            return entry.value

    def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
    ) -> bool:
        """Set value in cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl: TTL in seconds (None to use default, -1 for no expiration)

        Returns:
            True if successful
        """
        with self._lock:
            # Determine TTL
            if ttl == -1:
                ttl_seconds = None
            else:
                ttl_seconds = ttl if ttl is not None else self.default_ttl

            # Create entry
            entry = CacheEntry(value, ttl_seconds)

            # If key exists, update and move to end
            if key in self._cache:
                self._cache.move_to_end(key)
                self._cache[key] = entry
                return True

            # Check size limit and evict if needed
            while len(self._cache) >= self.max_size:
                self._evict_oldest()

            # Add new entry
            self._cache[key] = entry
            return True

    def delete(self, key: str) -> bool:
        """Delete key from cache.

        Args:
            key: Cache key

        Returns:
            True if key was deleted, False if not found
        """
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    def clear(self) -> bool:
        """Clear all cache entries.

        Returns:
            True if successful
        """
        with self._lock:
            self._cache.clear()
            return True

    def exists(self, key: str) -> bool:
        """Check if key exists and is not expired.

        Args:
            key: Cache key

        Returns:
            True if key exists and is valid
        """
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return False
            if entry.is_expired():
                del self._cache[key]
                return False
            return True

    def get_or_set(
        self,
        key: str,
        factory: Callable[[], Any],
        ttl: Optional[int] = None,
    ) -> Any:
        """Get from cache or set using factory function.

        Args:
            key: Cache key
            factory: Function to create value if not in cache
            ttl: TTL in seconds

        Returns:
            Cached or newly created value
        """
        # Try to get from cache
        value = self.get(key)
        if value is not None:
            return value

        # Create value
        value = factory()

        # Store in cache
        self.set(key, value, ttl)

        return value

    def get_many(self, keys: list) -> Dict[str, Any]:
        """Get multiple values from cache.

        Args:
            keys: List of cache keys

        Returns:
            Dictionary of found key-value pairs
        """
        result = {}
        for key in keys:
            value = self.get(key)
            if value is not None:
                result[key] = value
        return result

    def set_many(
        self,
        items: Dict[str, Any],
        ttl: Optional[int] = None,
    ) -> bool:
        """Set multiple values in cache.

        Args:
            items: Dictionary of key-value pairs
            ttl: TTL in seconds

        Returns:
            True if successful
        """
        for key, value in items.items():
            self.set(key, value, ttl)
        return True

    def delete_many(self, keys: list) -> int:
        """Delete multiple keys from cache.

        Args:
            keys: List of keys to delete

        Returns:
            Number of keys deleted
        """
        count = 0
        for key in keys:
            if self.delete(key):
                count += 1
        return count

    def keys(self) -> list:
        """Get all valid (non-expired) cache keys."""
        with self._lock:
            # Clean up expired entries first
            expired_keys = [
                key for key, entry in self._cache.items()
                if entry.is_expired()
            ]
            for key in expired_keys:
                del self._cache[key]

            return list(self._cache.keys())

    def size(self) -> int:
        """Get current cache size."""
        with self._lock:
            return len(self._cache)

    def stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self._lock:
            total_requests = self._hits + self._misses
            hit_rate = self._hits / total_requests if total_requests > 0 else 0

            return {
                "size": len(self._cache),
                "max_size": self.max_size,
                "hits": self._hits,
                "misses": self._misses,
                "evictions": self._evictions,
                "hit_rate": hit_rate,
                "default_ttl": self.default_ttl,
            }

    def _evict_oldest(self):
        """Evict oldest (least recently used) entry."""
        if self._cache:
            # Pop from beginning (oldest)
            self._cache.popitem(last=False)
            self._evictions += 1

    def cleanup_expired(self) -> int:
        """Remove all expired entries.

        Returns:
            Number of entries removed
        """
        with self._lock:
            expired_keys = [
                key for key, entry in self._cache.items()
                if entry.is_expired()
            ]

            for key in expired_keys:
                del self._cache[key]

            return len(expired_keys)


class EmbeddingCache(CacheManager):
    """Specialized cache for embeddings with content-based keys."""

    def __init__(
        self,
        max_size: int = 1000,
        default_ttl: Optional[int] = 3600,
    ):
        super().__init__(max_size, default_ttl)

    def _make_key(self, text: str, provider: str, model: str) -> str:
        """Generate cache key for embedding.

        Uses hash of text to avoid storing large keys.
        """
        import hashlib
        text_hash = hashlib.md5(text.encode()).hexdigest()
        return f"emb:{provider}:{model}:{text_hash}"

    def get_embedding(
        self,
        text: str,
        provider: str,
        model: str,
    ) -> Optional[list]:
        """Get cached embedding.

        Args:
            text: Original text
            provider: Embedding provider name
            model: Model name

        Returns:
            Cached embedding vector or None
        """
        key = self._make_key(text, provider, model)
        return self.get(key)

    def set_embedding(
        self,
        text: str,
        provider: str,
        model: str,
        embedding: list,
        ttl: Optional[int] = None,
    ) -> bool:
        """Cache embedding.

        Args:
            text: Original text
            provider: Embedding provider name
            model: Model name
            embedding: Embedding vector
            ttl: TTL in seconds

        Returns:
            True if successful
        """
        key = self._make_key(text, provider, model)
        return self.set(key, embedding, ttl)


class SearchCache(CacheManager):
    """Specialized cache for search results."""

    def __init__(
        self,
        max_size: int = 500,
        default_ttl: Optional[int] = 600,  # 10 minutes
    ):
        super().__init__(max_size, default_ttl)

    def _make_key(
        self,
        query: str,
        top_k: int,
        filters: Optional[Dict],
    ) -> str:
        """Generate cache key for search."""
        import hashlib
        filter_str = str(sorted(filters.items())) if filters else ""
        key_data = f"{query}:{top_k}:{filter_str}"
        return f"search:{hashlib.md5(key_data.encode()).hexdigest()}"

    def get_search_results(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict] = None,
    ) -> Optional[list]:
        """Get cached search results.

        Args:
            query: Search query
            top_k: Number of results
            filters: Search filters

        Returns:
            Cached results or None
        """
        key = self._make_key(query, top_k, filters)
        return self.get(key)

    def set_search_results(
        self,
        query: str,
        top_k: int,
        filters: Optional[Dict],
        results: list,
        ttl: Optional[int] = None,
    ) -> bool:
        """Cache search results.

        Args:
            query: Search query
            top_k: Number of results
            filters: Search filters
            results: Search results
            ttl: TTL in seconds

        Returns:
            True if successful
        """
        key = self._make_key(query, top_k, filters)
        return self.set(key, results, ttl)

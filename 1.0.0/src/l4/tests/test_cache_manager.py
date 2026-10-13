"""Tests for L4 Cache Manager."""
import pytest
import time
from src.l4.storage.cache_manager import (
    CacheManager,
    CacheEntry,
    EmbeddingCache,
    SearchCache,
)


class TestCacheEntry:
    """Tests for CacheEntry."""

    def test_init(self):
        """Test cache entry initialization."""
        entry = CacheEntry("value")
        assert entry.value == "value"
        assert entry.ttl_seconds is None
        assert entry.access_count == 1

    def test_init_with_ttl(self):
        """Test cache entry with TTL."""
        entry = CacheEntry("value", ttl_seconds=60)
        assert entry.ttl_seconds == 60

    def test_is_expired_no_ttl(self):
        """Test not expired when no TTL."""
        entry = CacheEntry("value")
        assert entry.is_expired() is False

    def test_is_expired_with_ttl(self):
        """Test expired with TTL."""
        entry = CacheEntry("value", ttl_seconds=1)
        time.sleep(1.1)
        assert entry.is_expired() is True

    def test_touch(self):
        """Test touching updates access metadata."""
        entry = CacheEntry("value")
        old_accessed = entry.last_accessed
        time.sleep(0.01)
        entry.touch()

        assert entry.access_count == 2
        assert entry.last_accessed > old_accessed


class TestCacheManager:
    """Tests for CacheManager."""

    def test_init_default(self):
        """Test default initialization."""
        cache = CacheManager()
        assert cache.max_size == 1000
        assert cache.default_ttl == 3600

    def test_init_custom(self):
        """Test custom initialization."""
        cache = CacheManager(max_size=100, default_ttl=300)
        assert cache.max_size == 100
        assert cache.default_ttl == 300

    def test_set_and_get(self):
        """Test setting and getting value."""
        cache = CacheManager()
        cache.set("key", "value")

        result = cache.get("key")
        assert result == "value"

    def test_get_nonexistent(self):
        """Test getting non-existent key."""
        cache = CacheManager()
        result = cache.get("nonexistent")
        assert result is None

    def test_get_expired(self):
        """Test getting expired value."""
        cache = CacheManager()
        cache.set("key", "value", ttl=1)
        time.sleep(1.1)

        result = cache.get("key")
        assert result is None

    def test_delete(self):
        """Test deleting key."""
        cache = CacheManager()
        cache.set("key", "value")

        result = cache.delete("key")
        assert result is True
        assert cache.get("key") is None

    def test_delete_nonexistent(self):
        """Test deleting non-existent key."""
        cache = CacheManager()
        result = cache.delete("nonexistent")
        assert result is False

    def test_clear(self):
        """Test clearing cache."""
        cache = CacheManager()
        cache.set("key1", "value1")
        cache.set("key2", "value2")

        cache.clear()

        assert cache.get("key1") is None
        assert cache.get("key2") is None
        assert cache.size() == 0

    def test_exists(self):
        """Test checking key existence."""
        cache = CacheManager()
        cache.set("key", "value")

        assert cache.exists("key") is True
        assert cache.exists("nonexistent") is False

    def test_lru_eviction(self):
        """Test LRU eviction when cache is full."""
        cache = CacheManager(max_size=3)
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.set("key3", "value3")

        # Access key1 to make it recently used
        cache.get("key1")

        # Add new key, should evict key2 (least recently used)
        cache.set("key4", "value4")

        assert cache.get("key1") is not None  # Still exists
        assert cache.get("key2") is None      # Evicted
        assert cache.get("key3") is not None  # Still exists
        assert cache.get("key4") is not None  # New

    def test_get_or_set(self):
        """Test get_or_set method."""
        cache = CacheManager()

        # First call should use factory
        value1 = cache.get_or_set("key", lambda: "computed")
        assert value1 == "computed"

        # Second call should return cached value
        value2 = cache.get_or_set("key", lambda: "different")
        assert value2 == "computed"  # Not "different"

    def test_get_many(self):
        """Test getting multiple values."""
        cache = CacheManager()
        cache.set("key1", "value1")
        cache.set("key2", "value2")

        results = cache.get_many(["key1", "key2", "key3"])

        assert results == {"key1": "value1", "key2": "value2"}

    def test_set_many(self):
        """Test setting multiple values."""
        cache = CacheManager()

        cache.set_many({"key1": "value1", "key2": "value2"})

        assert cache.get("key1") == "value1"
        assert cache.get("key2") == "value2"

    def test_delete_many(self):
        """Test deleting multiple keys."""
        cache = CacheManager()
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.set("key3", "value3")

        count = cache.delete_many(["key1", "key2", "nonexistent"])

        assert count == 2
        assert cache.get("key3") is not None

    def test_size(self):
        """Test getting cache size."""
        cache = CacheManager()
        assert cache.size() == 0

        cache.set("key", "value")
        assert cache.size() == 1

    def test_stats(self):
        """Test getting cache statistics."""
        cache = CacheManager(max_size=100)
        cache.set("key", "value")
        cache.get("key")  # Hit
        cache.get("nonexistent")  # Miss

        stats = cache.stats()

        assert stats["size"] == 1
        assert stats["max_size"] == 100
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["hit_rate"] == 0.5

    def test_cleanup_expired(self):
        """Test cleaning up expired entries."""
        cache = CacheManager()
        cache.set("key1", "value1", ttl=1)
        cache.set("key2", "value2", ttl=60)

        time.sleep(1.1)
        removed = cache.cleanup_expired()

        assert removed == 1
        assert cache.get("key1") is None
        assert cache.get("key2") is not None


class TestEmbeddingCache:
    """Tests for EmbeddingCache."""

    def test_make_key(self):
        """Test key generation."""
        cache = EmbeddingCache()
        key1 = cache._make_key("hello", "openai", "text-embedding-3-small")
        key2 = cache._make_key("hello", "openai", "text-embedding-3-small")
        key3 = cache._make_key("world", "openai", "text-embedding-3-small")

        assert key1 == key2  # Same text = same key
        assert key1 != key3  # Different text = different key

    def test_embedding_roundtrip(self):
        """Test embedding cache roundtrip."""
        cache = EmbeddingCache()
        embedding = [0.1, 0.2, 0.3]

        cache.set_embedding("text", "provider", "model", embedding)
        retrieved = cache.get_embedding("text", "provider", "model")

        assert retrieved == embedding


class TestSearchCache:
    """Tests for SearchCache."""

    def test_make_key(self):
        """Test key generation."""
        cache = SearchCache()
        key1 = cache._make_key("query", 5, None)
        key2 = cache._make_key("query", 5, None)
        key3 = cache._make_key("query", 10, None)

        assert key1 == key2
        assert key1 != key3

    def test_search_results_roundtrip(self):
        """Test search results cache roundtrip."""
        cache = SearchCache()
        results = ["result1", "result2"]

        cache.set_search_results("query", 5, None, results)
        retrieved = cache.get_search_results("query", 5, None)

        assert retrieved == results

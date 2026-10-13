"""Tests for L4 Memory Store."""
import pytest
import tempfile
import os
from src.l4.storage.memory_store import (
    MemoryCompressor,
    InMemoryStore,
    InMemoryConversationMemory,
    InMemoryUserPreferenceMemory,
    InMemoryKnowledgeMemory,
    FileMemoryStore,
    create_memory_store,
)


class TestMemoryCompressor:
    """Tests for MemoryCompressor."""

    def test_init_default(self):
        """Test default initialization."""
        compressor = MemoryCompressor()
        assert compressor.max_messages == 20
        assert compressor.compression_threshold == 10

    def test_init_custom(self):
        """Test custom initialization."""
        compressor = MemoryCompressor(max_messages=50, compression_threshold=20)
        assert compressor.max_messages == 50
        assert compressor.compression_threshold == 20

    def test_should_compress_false(self):
        """Test should_compress returns False for small message list."""
        compressor = MemoryCompressor(max_messages=10)
        messages = [{"role": "user", "content": f"msg{i}"} for i in range(5)]
        assert compressor.should_compress(messages) is False

    def test_should_compress_true(self):
        """Test should_compress returns True for large message list."""
        compressor = MemoryCompressor(max_messages=10)
        messages = [{"role": "user", "content": f"msg{i}"} for i in range(10)]
        assert compressor.should_compress(messages) is True

    def test_compress_reduces_size(self):
        """Test compression reduces message count."""
        compressor = MemoryCompressor(max_messages=10, compression_threshold=5)
        messages = [{"role": "user", "content": f"message {i}"} for i in range(10)]

        compressed = compressor.compress(messages)

        assert len(compressed) < len(messages)
        assert compressed[0].get("is_compressed") is True
        assert "[Earlier conversation summary]" in compressed[0]["content"]

    def test_compress_no_compress_if_small(self):
        """Test no compression if below threshold."""
        compressor = MemoryCompressor(max_messages=20)
        messages = [{"role": "user", "content": f"msg{i}"} for i in range(5)]

        compressed = compressor.compress(messages)

        assert len(compressed) == len(messages)
        assert not any(m.get("is_compressed") for m in compressed)

    def test_get_compression_stats(self):
        """Test getting compression statistics."""
        compressor = MemoryCompressor(max_messages=10, compression_threshold=5)
        messages = [{"role": "user", "content": f"message {i}"} for i in range(10)]
        compressed = compressor.compress(messages)

        stats = compressor.get_compression_stats(messages, compressed)

        assert stats["original_messages"] == 10
        assert stats["compressed_messages"] < 10
        assert stats["compression_ratio"] > 0
        assert "messages_summarized" in stats


class TestInMemoryStore:
    """Tests for InMemoryStore."""

    def test_init_default(self):
        """Test default initialization."""
        store = InMemoryStore()
        assert store.conversations == {}
        assert store.preferences == {}

    def test_save_conversation(self):
        """Test saving conversation."""
        store = InMemoryStore()
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi!"},
        ]

        result = store.save_conversation("session1", messages)

        assert result is True
        assert "session1" in store.conversations
        assert len(store.conversations["session1"]) == 2

    def test_save_conversation_empty_session(self):
        """Test saving conversation with empty session ID."""
        store = InMemoryStore()
        messages = [{"role": "user", "content": "Hello"}]

        result = store.save_conversation("", messages)

        assert result is False

    def test_save_conversation_with_compression(self):
        """Test saving conversation triggers compression."""
        compressor = MemoryCompressor(max_messages=5, compression_threshold=3)
        store = InMemoryStore(compressor=compressor)

        # Add enough messages to trigger compression
        messages = [{"role": "user", "content": f"msg{i}"} for i in range(5)]
        result = store.save_conversation("session1", messages)

        assert result is True
        # Should be compressed to threshold + 1 (for summary)
        assert len(store.conversations["session1"]) <= 4

    def test_load_conversation(self):
        """Test loading conversation."""
        store = InMemoryStore()
        messages = [{"role": "user", "content": f"msg{i}"} for i in range(10)]
        store.save_conversation("session1", messages)

        loaded = store.load_conversation("session1", limit=5)

        assert len(loaded) == 5
        # Should get last 5 messages
        assert loaded[0]["content"] == "msg5"
        assert loaded[4]["content"] == "msg9"

    def test_load_conversation_nonexistent(self):
        """Test loading non-existent conversation."""
        store = InMemoryStore()
        loaded = store.load_conversation("nonexistent")
        assert loaded == []

    def test_load_conversation_empty_session(self):
        """Test loading conversation with empty session ID."""
        store = InMemoryStore()
        loaded = store.load_conversation("")
        assert loaded == []

    def test_save_preference(self):
        """Test saving user preference."""
        store = InMemoryStore()

        result = store.save_preference("user1", "theme", "dark")

        assert result is True
        assert store.preferences["user1"]["theme"]["value"] == "dark"

    def test_load_preference(self):
        """Test loading user preference."""
        store = InMemoryStore()
        store.save_preference("user1", "theme", "dark")

        value = store.load_preference("user1", "theme")

        assert value == "dark"

    def test_load_preference_default(self):
        """Test loading non-existent preference with default."""
        store = InMemoryStore()

        value = store.load_preference("user1", "nonexistent", default="default_value")

        assert value == "default_value"

    def test_delete_session(self):
        """Test deleting session."""
        store = InMemoryStore()
        store.save_conversation("session1", [{"role": "user", "content": "Hi"}])

        result = store.delete_session("session1")

        assert result is True
        assert "session1" not in store.conversations

    def test_list_sessions(self):
        """Test listing sessions."""
        store = InMemoryStore()
        store.save_conversation("session1", [{"role": "user", "content": "Hi"}])
        store.save_conversation("session2", [{"role": "user", "content": "Hello"}])

        sessions = store.list_sessions()

        assert len(sessions) == 2
        assert all("session_id" in s for s in sessions)

    def test_get_full_conversation(self):
        """Test getting full conversation."""
        store = InMemoryStore()
        messages = [{"role": "user", "content": f"msg{i}"} for i in range(10)]
        store.save_conversation("session1", messages)

        full = store.get_full_conversation("session1")

        assert len(full) == 10

    def test_force_compress(self):
        """Test forcing compression."""
        store = InMemoryStore()
        messages = [{"role": "user", "content": f"msg{i}"} for i in range(10)]
        store.save_conversation("session1", messages)

        result = store.force_compress("session1")

        assert result is True

    def test_get_compression_stats(self):
        """Test getting compression stats."""
        compressor = MemoryCompressor(max_messages=5, compression_threshold=3)
        store = InMemoryStore(compressor=compressor)
        messages = [{"role": "user", "content": f"msg{i}"} for i in range(5)]
        store.save_conversation("session1", messages)

        stats = store.get_compression_stats("session1")

        assert len(stats) > 0


class TestFileMemoryStore:
    """Tests for FileMemoryStore."""

    def test_save_and_load_conversation(self):
        """Test saving and loading conversation from file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = FileMemoryStore(storage_dir=tmpdir)
            messages = [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi!"},
            ]

            store.save_conversation("session1", messages)
            loaded = store.load_conversation("session1")

            assert len(loaded) == 2
            assert loaded[0]["content"] == "Hello"

    def test_persistence(self):
        """Test data persists across store instances."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store1 = FileMemoryStore(storage_dir=tmpdir)
            messages = [{"role": "user", "content": "Test"}]
            store1.save_conversation("session1", messages)

            # Create new store instance
            store2 = FileMemoryStore(storage_dir=tmpdir)
            loaded = store2.load_conversation("session1")

            assert len(loaded) == 1
            assert loaded[0]["content"] == "Test"

    def test_delete_session(self):
        """Test deleting session removes file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = FileMemoryStore(storage_dir=tmpdir)
            store.save_conversation("session1", [{"role": "user", "content": "Hi"}])

            store.delete_session("session1")
            loaded = store.load_conversation("session1")

            assert loaded == []

    def test_save_preference(self):
        """Test saving preference to file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = FileMemoryStore(storage_dir=tmpdir)
            store.save_preference("user1", "theme", "dark")

            value = store.load_preference("user1", "theme")
            assert value == "dark"


class TestCreateMemoryStore:
    """Tests for create_memory_store factory."""

    def test_create_memory(self):
        """Test creating in-memory store."""
        store = create_memory_store("memory")
        assert isinstance(store, InMemoryStore)

    def test_create_file(self):
        """Test creating file store."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = create_memory_store("file", storage_dir=tmpdir)
            assert isinstance(store, FileMemoryStore)

    def test_create_unsupported(self):
        """Test creating unsupported store raises error."""
        with pytest.raises(ValueError) as exc_info:
            create_memory_store("unsupported")
        assert "Unsupported memory store type" in str(exc_info.value)


class TestInMemoryConversationMemory:
    """Tests for InMemoryConversationMemory (extracted from unified MemoryStore)."""

    def test_init_default(self):
        """Test default initialization."""
        memory = InMemoryConversationMemory()
        assert memory.conversations == {}
        assert memory.session_metadata == {}

    def test_save_and_load_conversation(self):
        """Test saving and loading conversation."""
        memory = InMemoryConversationMemory()
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi!"},
        ]
        result = memory.save_conversation("session1", messages)
        assert result is True

        loaded = memory.load_conversation("session1")
        assert len(loaded) == 2
        assert loaded[0]["content"] == "Hello"

    def test_delete_session(self):
        """Test deleting session."""
        memory = InMemoryConversationMemory()
        memory.save_conversation("session1", [{"role": "user", "content": "Hi"}])

        result = memory.delete_session("session1")
        assert result is True
        assert "session1" not in memory.conversations

    def test_list_sessions(self):
        """Test listing sessions."""
        memory = InMemoryConversationMemory()
        memory.save_conversation("session1", [{"role": "user", "content": "Hi"}])
        memory.save_conversation("session2", [{"role": "user", "content": "Hello"}])

        sessions = memory.list_sessions()
        assert len(sessions) == 2
        assert all("session_id" in s for s in sessions)

    def test_compression(self):
        """Test conversation compression."""
        compressor = MemoryCompressor(max_messages=5, compression_threshold=3)
        memory = InMemoryConversationMemory(compressor=compressor)
        messages = [{"role": "user", "content": f"msg{i}"} for i in range(5)]

        memory.save_conversation("session1", messages)
        assert len(memory.conversations["session1"]) <= 4

        stats = memory.get_compression_stats("session1")
        assert len(stats) > 0


class TestInMemoryUserPreferenceMemory:
    """Tests for InMemoryUserPreferenceMemory (extracted from unified MemoryStore)."""

    def test_init_default(self):
        """Test default initialization."""
        memory = InMemoryUserPreferenceMemory()
        assert memory.preferences == {}

    def test_save_and_load_preference(self):
        """Test saving and loading preference."""
        memory = InMemoryUserPreferenceMemory()
        result = memory.save_preference("user1", "theme", "dark")
        assert result is True

        value = memory.load_preference("user1", "theme")
        assert value == "dark"

    def test_load_preference_default(self):
        """Test loading non-existent preference with default."""
        memory = InMemoryUserPreferenceMemory()
        value = memory.load_preference("user1", "nonexistent", default="default_value")
        assert value == "default_value"

    def test_get_all_preferences(self):
        """Test getting all preferences for a user."""
        memory = InMemoryUserPreferenceMemory()
        memory.save_preference("user1", "theme", "dark")
        memory.save_preference("user1", "language", "zh")

        prefs = memory.get_all_preferences("user1")
        assert prefs == {"theme": "dark", "language": "zh"}

    def test_delete_preference(self):
        """Test deleting a preference."""
        memory = InMemoryUserPreferenceMemory()
        memory.save_preference("user1", "theme", "dark")

        result = memory.delete_preference("user1", "theme")
        assert result is True
        assert memory.load_preference("user1", "theme") is None


class TestInMemoryKnowledgeMemory:
    """Tests for InMemoryKnowledgeMemory."""

    def test_init_default(self):
        """Test default initialization."""
        memory = InMemoryKnowledgeMemory()
        assert memory.knowledge == {}
        assert memory.get_knowledge_count() == 0

    def test_store_and_retrieve_knowledge(self):
        """Test storing and retrieving knowledge."""
        memory = InMemoryKnowledgeMemory()
        result = memory.store_knowledge(
            "k1",
            "Python is a programming language",
            {"category": "tech", "source": "wiki"}
        )
        assert result is True
        assert memory.get_knowledge_count() == 1

        retrieved = memory.retrieve_knowledge("k1")
        assert retrieved is not None
        assert retrieved["knowledge_id"] == "k1"
        assert "Python is a programming language" in retrieved["content_summary"]

    def test_list_knowledge(self):
        """Test listing knowledge entries."""
        memory = InMemoryKnowledgeMemory()
        memory.store_knowledge("k1", "Content 1", {"category": "tech"})
        memory.store_knowledge("k2", "Content 2", {"category": "science"})

        all_entries = memory.list_knowledge()
        assert len(all_entries) == 2

        tech_entries = memory.list_knowledge(category="tech")
        assert len(tech_entries) == 1
        assert tech_entries[0]["knowledge_id"] == "k1"

    def test_delete_knowledge(self):
        """Test deleting knowledge entry."""
        memory = InMemoryKnowledgeMemory()
        memory.store_knowledge("k1", "Content", {})

        result = memory.delete_knowledge("k1")
        assert result is True
        assert memory.retrieve_knowledge("k1") is None
        assert memory.get_knowledge_count() == 0

    def test_retrieve_nonexistent(self):
        """Test retrieving non-existent knowledge."""
        memory = InMemoryKnowledgeMemory()
        result = memory.retrieve_knowledge("nonexistent")
        assert result is None

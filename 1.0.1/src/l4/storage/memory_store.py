"""L4: Memory Store - Conversation and preference storage with compression."""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging
import json
import os

logger = logging.getLogger(__name__)


class MemoryCompressor:
    """Memory compressor for compressing conversation history."""

    def __init__(self, max_messages: int = 20, compression_threshold: int = 10):
        """
        Args:
            max_messages: Maximum messages before triggering compression
            compression_threshold: Number of oldest messages to compress when triggered
        """
        self.max_messages = max_messages
        self.compression_threshold = compression_threshold

    def should_compress(self, messages: List[Dict]) -> bool:
        """Check if messages should be compressed."""
        return len(messages) >= self.max_messages

    def compress(self, messages: List[Dict]) -> List[Dict]:
        """Compress messages by summarizing oldest ones.

        Returns:
            Compressed message list with:
            - A summary message at the beginning
            - Recent messages that weren't compressed
        """
        if not self.should_compress(messages):
            return messages

        # Split messages into those to compress and those to keep
        num_to_compress = len(messages) - self.compression_threshold
        messages_to_compress = messages[:num_to_compress]
        messages_to_keep = messages[num_to_compress:]

        # Generate summary of compressed messages
        summary = self._generate_summary(messages_to_compress)

        # Create compressed result
        compressed = [
            {
                "role": "system",
                "content": f"[Earlier conversation summary]: {summary}",
                "is_compressed": True,
                "original_count": len(messages_to_compress),
                "timestamp": datetime.now().timestamp(),
            }
        ]
        compressed.extend(messages_to_keep)

        return compressed

    def _generate_summary(self, messages: List[Dict]) -> str:
        """Generate a summary of messages.

        In a real implementation, this could use an LLM.
        For now, use a simple extractive summary.
        """
        if not messages:
            return ""

        # Extract key points (user questions and assistant main points)
        key_points = []
        for msg in messages:
            content = msg.get("content", "")
            role = msg.get("role", "")

            if role == "user":
                # Truncate long user messages
                if len(content) > 100:
                    content = content[:97] + "..."
                key_points.append(f"User asked: {content}")
            elif role == "assistant":
                # Extract first sentence or truncate
                first_sentence = content.split(".")[0] if "." in content else content[:100]
                if len(first_sentence) > 100:
                    first_sentence = first_sentence[:97] + "..."
                key_points.append(f"Assistant responded about: {first_sentence}")

        # Limit number of key points
        if len(key_points) > 5:
            key_points = key_points[:2] + ["..."] + key_points[-2:]

        return " | ".join(key_points)

    def get_compression_stats(self, original: List[Dict], compressed: List[Dict]) -> Dict:
        """Get compression statistics."""
        original_tokens = sum(len(m.get("content", "")) for m in original)
        compressed_tokens = sum(len(m.get("content", "")) for m in compressed)

        return {
            "original_messages": len(original),
            "compressed_messages": len(compressed),
            "original_length": original_tokens,
            "compressed_length": compressed_tokens,
            "compression_ratio": compressed_tokens / original_tokens if original_tokens > 0 else 1.0,
            "messages_summarized": len(original) - len(compressed) + 1,  # +1 for summary message
            "timestamp": datetime.now().timestamp(),
        }


class ConversationMemory(ABC):
    """Abstract base class for conversation memory storage."""

    @abstractmethod
    def save_conversation(
        self,
        session_id: str,
        messages: List[Dict[str, Any]]
    ) -> bool:
        """Save conversation history.

        Args:
            session_id: Session identifier
            messages: List of message dictionaries

        Returns:
            True if successful
        """
        pass

    @abstractmethod
    def load_conversation(
        self,
        session_id: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Load conversation history.

        Args:
            session_id: Session identifier
            limit: Maximum number of messages to return

        Returns:
            List of message dictionaries
        """
        pass

    @abstractmethod
    def delete_session(self, session_id: str) -> bool:
        """Delete a session and its history.

        Args:
            session_id: Session identifier

        Returns:
            True if successful
        """
        pass

    @abstractmethod
    def list_sessions(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """List available sessions.

        Args:
            user_id: Optional user ID to filter by

        Returns:
            List of session information dictionaries
        """
        pass


class UserPreferenceMemory(ABC):
    """Abstract base class for user preference storage."""

    @abstractmethod
    def save_preference(
        self,
        user_id: str,
        key: str,
        value: Any
    ) -> bool:
        """Save user preference.

        Args:
            user_id: User identifier
            key: Preference key
            value: Preference value

        Returns:
            True if successful
        """
        pass

    @abstractmethod
    def load_preference(
        self,
        user_id: str,
        key: str,
        default: Any = None
    ) -> Any:
        """Load user preference.

        Args:
            user_id: User identifier
            key: Preference key
            default: Default value if not found

        Returns:
            Preference value or default
        """
        pass


class KnowledgeMemory(ABC):
    """Abstract base class for system knowledge base storage.

    Note: Actual knowledge content is stored in VectorStore.
    This class manages knowledge metadata and catalog.
    """

    @abstractmethod
    def store_knowledge(
        self,
        knowledge_id: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Store knowledge entry metadata.

        Args:
            knowledge_id: Unique knowledge identifier
            content: Knowledge content summary
            metadata: Additional metadata (category, source, etc.)

        Returns:
            True if successful
        """
        pass

    @abstractmethod
    def retrieve_knowledge(
        self,
        knowledge_id: str
    ) -> Optional[Dict[str, Any]]:
        """Retrieve knowledge entry metadata.

        Args:
            knowledge_id: Knowledge identifier

        Returns:
            Knowledge metadata or None
        """
        pass

    @abstractmethod
    def list_knowledge(
        self,
        category: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List knowledge entries.

        Args:
            category: Optional category filter

        Returns:
            List of knowledge metadata dictionaries
        """
        pass

    @abstractmethod
    def delete_knowledge(self, knowledge_id: str) -> bool:
        """Delete knowledge entry.

        Args:
            knowledge_id: Knowledge identifier

        Returns:
            True if successful
        """
        pass


class MemoryStore(ConversationMemory, UserPreferenceMemory, ABC):
    """Abstract base class for unified memory stores.

    Combines ConversationMemory and UserPreferenceMemory for backward compatibility.
    New code should use specialized classes (ConversationMemory, UserPreferenceMemory,
    KnowledgeMemory) directly.
    """
    pass


class InMemoryStore(MemoryStore):
    """In-memory conversation store with compression."""

    def __init__(self, compressor: Optional[MemoryCompressor] = None):
        self.conversations: Dict[str, List[Dict]] = {}  # session_id -> messages
        self.preferences: Dict[str, Dict[str, Any]] = {}  # user_id -> {key: value}
        self.session_metadata: Dict[str, Dict[str, Any]] = {}  # session_id -> metadata
        self.compressor = compressor or MemoryCompressor(
            max_messages=20,
            compression_threshold=10
        )
        self.compression_stats: Dict[str, List[Dict]] = {}  # session_id -> stats history

    def save_conversation(self, session_id: str, messages: List[Dict[str, Any]]) -> bool:
        """Save conversation, with compression if needed."""
        if not session_id:
            logger.warning("Cannot save conversation without session_id")
            return False

        # Check if compression is needed
        if self.compressor.should_compress(messages):
            compressed = self.compressor.compress(messages)
            stats = self.compressor.get_compression_stats(messages, compressed)

            # Store stats
            if session_id not in self.compression_stats:
                self.compression_stats[session_id] = []
            self.compression_stats[session_id].append(stats)

            self.conversations[session_id] = compressed
            logger.debug(f"Compressed session {session_id}: {stats['compression_ratio']:.2f} ratio")
        else:
            self.conversations[session_id] = messages

        # Update metadata
        if session_id not in self.session_metadata:
            self.session_metadata[session_id] = {
                "created_at": datetime.now().timestamp(),
                "message_count": len(messages),
            }
        else:
            self.session_metadata[session_id]["last_active"] = datetime.now().timestamp()
            self.session_metadata[session_id]["message_count"] = len(messages)

        return True

    def load_conversation(self, session_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Load conversation."""
        if not session_id:
            return []

        messages = self.conversations.get(session_id, [])

        # If messages contain compressed summary, handle appropriately
        if messages and messages[0].get("is_compressed"):
            # Return all messages (including summary) up to limit
            return messages[-limit:] if len(messages) > limit else messages

        return messages[-limit:] if messages else []

    def get_full_conversation(self, session_id: str) -> List[Dict]:
        """Get full conversation history including compressed parts."""
        return self.conversations.get(session_id, [])

    def save_preference(self, user_id: str, key: str, value: Any) -> bool:
        """Save user preference."""
        if user_id not in self.preferences:
            self.preferences[user_id] = {}

        self.preferences[user_id][key] = {
            "value": value,
            "updated_at": datetime.now().timestamp(),
        }
        return True

    def load_preference(self, user_id: str, key: str, default: Any = None) -> Any:
        """Load user preference."""
        user_prefs = self.preferences.get(user_id, {})
        pref = user_prefs.get(key, {})
        return pref.get("value", default)

    def get_all_preferences(self, user_id: str) -> Dict[str, Any]:
        """Get all preferences for a user."""
        user_prefs = self.preferences.get(user_id, {})
        return {k: v.get("value") for k, v in user_prefs.items()}

    def delete_session(self, session_id: str) -> bool:
        """Delete a session."""
        if session_id in self.conversations:
            del self.conversations[session_id]
        if session_id in self.session_metadata:
            del self.session_metadata[session_id]
        if session_id in self.compression_stats:
            del self.compression_stats[session_id]
        return True

    def list_sessions(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """List sessions."""
        sessions = []

        for session_id, metadata in self.session_metadata.items():
            # If user_id specified, filter by it
            if user_id and metadata.get("user_id") != user_id:
                continue

            session_info = {
                "session_id": session_id,
                "created_at": metadata.get("created_at"),
                "last_active": metadata.get("last_active", metadata.get("created_at")),
                "message_count": metadata.get("message_count", 0),
            }
            sessions.append(session_info)

        # Sort by last_active (descending)
        sessions.sort(key=lambda x: x.get("last_active", 0), reverse=True)
        return sessions

    def get_compression_stats(self, session_id: str) -> List[Dict]:
        """Get compression statistics for a session."""
        return self.compression_stats.get(session_id, [])

    def force_compress(self, session_id: str) -> bool:
        """Force compression of a session's history."""
        if session_id not in self.conversations:
            return False

        messages = self.conversations[session_id]
        compressed = self.compressor.compress(messages)
        stats = self.compressor.get_compression_stats(messages, compressed)

        if session_id not in self.compression_stats:
            self.compression_stats[session_id] = []
        self.compression_stats[session_id].append(stats)

        self.conversations[session_id] = compressed
        return True


class FileMemoryStore(MemoryStore):
    """File-based memory store for persistence."""

    def __init__(
        self,
        storage_dir: str = ".memory",
        compressor: Optional[MemoryCompressor] = None,
    ):
        self.storage_dir = storage_dir
        self.compressor = compressor or MemoryCompressor()

        # Ensure storage directory exists
        os.makedirs(storage_dir, exist_ok=True)
        os.makedirs(os.path.join(storage_dir, "conversations"), exist_ok=True)
        os.makedirs(os.path.join(storage_dir, "preferences"), exist_ok=True)

    def _get_conversation_path(self, session_id: str) -> str:
        """Get file path for conversation."""
        return os.path.join(self.storage_dir, "conversations", f"{session_id}.json")

    def _get_preferences_path(self, user_id: str) -> str:
        """Get file path for preferences."""
        return os.path.join(self.storage_dir, "preferences", f"{user_id}.json")

    def save_conversation(self, session_id: str, messages: List[Dict[str, Any]]) -> bool:
        """Save conversation to file."""
        if not session_id:
            return False

        # Apply compression if needed
        if self.compressor.should_compress(messages):
            messages = self.compressor.compress(messages)

        filepath = self._get_conversation_path(session_id)

        data = {
            "session_id": session_id,
            "messages": messages,
            "updated_at": datetime.now().timestamp(),
            "message_count": len(messages),
        }

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logger.error(f"Failed to save conversation: {e}")
            return False

    def load_conversation(self, session_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Load conversation from file."""
        filepath = self._get_conversation_path(session_id)

        if not os.path.exists(filepath):
            return []

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)

            messages = data.get("messages", [])

            # Handle compressed messages
            if messages and messages[0].get("is_compressed"):
                return messages[-limit:] if len(messages) > limit else messages

            return messages[-limit:] if messages else []
        except Exception as e:
            logger.error(f"Failed to load conversation: {e}")
            return []

    def save_preference(self, user_id: str, key: str, value: Any) -> bool:
        """Save preference to file."""
        filepath = self._get_preferences_path(user_id)

        # Load existing preferences
        prefs = {}
        if os.path.exists(filepath):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    prefs = json.load(f)
            except Exception:
                pass

        # Update preference
        prefs[key] = {
            "value": value,
            "updated_at": datetime.now().timestamp(),
        }

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(prefs, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logger.error(f"Failed to save preference: {e}")
            return False

    def load_preference(self, user_id: str, key: str, default: Any = None) -> Any:
        """Load preference from file."""
        filepath = self._get_preferences_path(user_id)

        if not os.path.exists(filepath):
            return default

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                prefs = json.load(f)

            pref = prefs.get(key, {})
            return pref.get("value", default)
        except Exception as e:
            logger.error(f"Failed to load preference: {e}")
            return default

    def delete_session(self, session_id: str) -> bool:
        """Delete session file."""
        filepath = self._get_conversation_path(session_id)

        if os.path.exists(filepath):
            try:
                os.remove(filepath)
                return True
            except Exception as e:
                logger.error(f"Failed to delete session: {e}")
                return False
        return True

    def list_sessions(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """List sessions from files."""
        sessions = []
        conversations_dir = os.path.join(self.storage_dir, "conversations")

        if not os.path.exists(conversations_dir):
            return sessions

        for filename in os.listdir(conversations_dir):
            if not filename.endswith(".json"):
                continue

            session_id = filename[:-5]  # Remove .json
            filepath = os.path.join(conversations_dir, filename)

            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)

                # Filter by user_id if specified
                if user_id:
                    first_msg = data.get("messages", [{}])[0]
                    msg_user_id = first_msg.get("metadata", {}).get("user_id")
                    if msg_user_id != user_id:
                        continue

                sessions.append({
                    "session_id": session_id,
                    "created_at": data.get("updated_at", 0),
                    "last_active": data.get("updated_at", 0),
                    "message_count": data.get("message_count", 0),
                })
            except Exception:
                continue

        # Sort by last_active (descending)
        sessions.sort(key=lambda x: x.get("last_active", 0), reverse=True)
        return sessions


class InMemoryConversationMemory(ConversationMemory):
    """In-memory conversation memory storage (extracted from unified MemoryStore)."""

    def __init__(self, compressor: Optional[MemoryCompressor] = None):
        self.conversations: Dict[str, List[Dict]] = {}
        self.session_metadata: Dict[str, Dict[str, Any]] = {}
        self.compression_stats: Dict[str, List[Dict]] = {}
        self.compressor = compressor or MemoryCompressor(
            max_messages=20,
            compression_threshold=10,
        )

    def save_conversation(self, session_id: str, messages: List[Dict[str, Any]]) -> bool:
        """Save conversation, with compression if needed."""
        if not session_id:
            logger.warning("Cannot save conversation without session_id")
            return False

        if self.compressor.should_compress(messages):
            compressed = self.compressor.compress(messages)
            stats = self.compressor.get_compression_stats(messages, compressed)
            if session_id not in self.compression_stats:
                self.compression_stats[session_id] = []
            self.compression_stats[session_id].append(stats)
            self.conversations[session_id] = compressed
            logger.debug(f"Compressed session {session_id}: {stats['compression_ratio']:.2f} ratio")
        else:
            self.conversations[session_id] = messages

        if session_id not in self.session_metadata:
            self.session_metadata[session_id] = {
                "created_at": datetime.now().timestamp(),
                "message_count": len(messages),
            }
        else:
            self.session_metadata[session_id]["last_active"] = datetime.now().timestamp()
            self.session_metadata[session_id]["message_count"] = len(messages)

        return True

    def load_conversation(self, session_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Load conversation."""
        if not session_id:
            return []
        messages = self.conversations.get(session_id, [])
        if messages and messages[0].get("is_compressed"):
            return messages[-limit:] if len(messages) > limit else messages
        return messages[-limit:] if messages else []

    def get_full_conversation(self, session_id: str) -> List[Dict]:
        """Get full conversation history including compressed parts."""
        return self.conversations.get(session_id, [])

    def delete_session(self, session_id: str) -> bool:
        """Delete a session."""
        if session_id in self.conversations:
            del self.conversations[session_id]
        if session_id in self.session_metadata:
            del self.session_metadata[session_id]
        if session_id in self.compression_stats:
            del self.compression_stats[session_id]
        return True

    def list_sessions(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """List sessions."""
        sessions = []
        for session_id, metadata in self.session_metadata.items():
            if user_id and metadata.get("user_id") != user_id:
                continue
            sessions.append({
                "session_id": session_id,
                "created_at": metadata.get("created_at"),
                "last_active": metadata.get("last_active", metadata.get("created_at")),
                "message_count": metadata.get("message_count", 0),
            })
        sessions.sort(key=lambda x: x.get("last_active", 0), reverse=True)
        return sessions

    def get_compression_stats(self, session_id: str) -> List[Dict]:
        """Get compression statistics for a session."""
        return self.compression_stats.get(session_id, [])

    def force_compress(self, session_id: str) -> bool:
        """Force compression of a session's history."""
        if session_id not in self.conversations:
            return False
        messages = self.conversations[session_id]
        compressed = self.compressor.compress(messages)
        stats = self.compressor.get_compression_stats(messages, compressed)
        if session_id not in self.compression_stats:
            self.compression_stats[session_id] = []
        self.compression_stats[session_id].append(stats)
        self.conversations[session_id] = compressed
        return True


class InMemoryUserPreferenceMemory(UserPreferenceMemory):
    """In-memory user preference storage (extracted from unified MemoryStore)."""

    def __init__(self):
        self.preferences: Dict[str, Dict[str, Any]] = {}

    def save_preference(self, user_id: str, key: str, value: Any) -> bool:
        """Save user preference."""
        if user_id not in self.preferences:
            self.preferences[user_id] = {}
        self.preferences[user_id][key] = {
            "value": value,
            "updated_at": datetime.now().timestamp(),
        }
        return True

    def load_preference(self, user_id: str, key: str, default: Any = None) -> Any:
        """Load user preference."""
        user_prefs = self.preferences.get(user_id, {})
        pref = user_prefs.get(key, {})
        return pref.get("value", default)

    def get_all_preferences(self, user_id: str) -> Dict[str, Any]:
        """Get all preferences for a user."""
        user_prefs = self.preferences.get(user_id, {})
        return {k: v.get("value") for k, v in user_prefs.items()}

    def delete_preference(self, user_id: str, key: str) -> bool:
        """Delete a user preference."""
        user_prefs = self.preferences.get(user_id, {})
        if key in user_prefs:
            del user_prefs[key]
            return True
        return False


class InMemoryKnowledgeMemory(KnowledgeMemory):
    """In-memory knowledge base metadata storage.

    Note: Actual knowledge embeddings are stored in VectorStore.
    This class manages knowledge catalog metadata.
    """

    def __init__(self):
        self.knowledge: Dict[str, Dict[str, Any]] = {}

    def store_knowledge(
        self,
        knowledge_id: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Store knowledge entry metadata."""
        self.knowledge[knowledge_id] = {
            "knowledge_id": knowledge_id,
            "content_summary": content[:200] if len(content) > 200 else content,
            "metadata": metadata or {},
            "created_at": datetime.now().timestamp(),
            "updated_at": datetime.now().timestamp(),
        }
        return True

    def retrieve_knowledge(self, knowledge_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve knowledge entry metadata."""
        return self.knowledge.get(knowledge_id)

    def list_knowledge(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """List knowledge entries."""
        results = []
        for entry in self.knowledge.values():
            if category:
                entry_category = entry.get("metadata", {}).get("category")
                if entry_category != category:
                    continue
            results.append(entry)
        return results

    def delete_knowledge(self, knowledge_id: str) -> bool:
        """Delete knowledge entry."""
        if knowledge_id in self.knowledge:
            del self.knowledge[knowledge_id]
            return True
        return False

    def get_knowledge_count(self) -> int:
        """Get total knowledge entry count."""
        return len(self.knowledge)


def create_memory_store(
    store_type: str = "memory",
    **kwargs
) -> MemoryStore:
    """Factory function to create memory store.

    Args:
        store_type: Type of store ('memory', 'file')
        **kwargs: Store-specific arguments

    Returns:
        MemoryStore instance

    Raises:
        ValueError: If store_type is not supported
    """
    store_type = store_type.lower()

    if store_type == "memory":
        return InMemoryStore(**kwargs)
    elif store_type == "file":
        return FileMemoryStore(**kwargs)
    else:
        raise ValueError(
            f"Unsupported memory store type: {store_type}. "
            f"Supported: memory, file"
        )

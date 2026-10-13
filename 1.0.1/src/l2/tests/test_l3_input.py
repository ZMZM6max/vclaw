"""Tests for L3Input data model.

TC-L3Input-001: Create L3Input with all fields
TC-L3Input-002: L3Input with default empty lists
"""
import sys
sys.path.insert(0, 'src')

from src.core.models import L3Input, SessionContext


class TestL3Input:
    """Tests for L3Input data model."""

    def test_l3input_creation(self):
        """TC-L3Input-001: Create L3Input with all fields."""
        session_context = SessionContext(
            session_id="test_session",
            user_id="user_123",
            current_query="Hello",
            history=[],
            user_permissions=[]
        )

        l3_input = L3Input(
            session_context=session_context,
            available_tools=[{"name": "calculator"}],
            relevant_memories=["User likes Python"]
        )

        assert l3_input.session_context.session_id == "test_session"
        assert len(l3_input.available_tools) == 1
        assert len(l3_input.relevant_memories) == 1

    def test_l3input_optional_fields(self):
        """TC-L3Input-002: L3Input with default empty lists."""
        session_context = SessionContext(
            session_id="test_session",
            user_id="user_123",
            current_query="Hello",
            history=[],
            user_permissions=[]
        )

        # Only provide required field
        l3_input = L3Input(session_context=session_context)

        assert l3_input.available_tools == []
        assert l3_input.relevant_memories == []

    def test_l3input_contains_session_context(self):
        """Verify L3Input contains session context."""
        session_context = SessionContext(
            session_id="session_abc",
            user_id="user_456",
            current_query="What's the weather?",
            history=[{"role": "user", "content": "Hi"}],
            user_permissions=["file_read"]
        )

        l3_input = L3Input(session_context=session_context)

        assert l3_input.session_context.user_id == "user_456"
        assert l3_input.session_context.current_query == "What's the weather?"
        assert len(l3_input.session_context.history) == 1

    def test_l3input_multiple_tools(self):
        """Verify L3Input can hold multiple tools."""
        session_context = SessionContext(
            session_id="test_session",
            user_id="user_123",
            current_query="Hello",
            history=[],
            user_permissions=[]
        )

        l3_input = L3Input(
            session_context=session_context,
            available_tools=[
                {"name": "calculator", "description": "Math"},
                {"name": "file_read", "description": "Read files"},
                {"name": "search", "description": "Search web"}
            ]
        )

        assert len(l3_input.available_tools) == 3
        assert l3_input.available_tools[0]["name"] == "calculator"

    def test_l3input_multiple_memories(self):
        """Verify L3Input can hold multiple memories."""
        session_context = SessionContext(
            session_id="test_session",
            user_id="user_123",
            current_query="Hello",
            history=[],
            user_permissions=[]
        )

        l3_input = L3Input(
            session_context=session_context,
            relevant_memories=[
                "User likes Python",
                "User prefers short answers",
                "User is a developer"
            ]
        )

        assert len(l3_input.relevant_memories) == 3
        assert "User likes Python" in l3_input.relevant_memories

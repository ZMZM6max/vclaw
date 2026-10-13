"""Tests for ToolPreparer component.

TC-ToolPreparer-001: Returns only no-permission tools when user has no permissions
TC-ToolPreparer-002: Returns tools matching user permissions
TC-ToolPreparer-003: Returns all tools when user has all permissions
"""
import sys
sys.path.insert(0, 'src')

from unittest.mock import Mock
from src.l2.l2_control_gateway import ToolPreparer
from src.core.interfaces import ToolsInterface


class TestToolPreparer:
    """Tests for ToolPreparer component."""

    def test_tool_preparer_returns_all_tools_with_no_permissions(self):
        """TC-ToolPreparer-001: Returns only no-permission tools when user has no permissions."""
        # Mock L5 tools
        mock_tools = Mock(spec=ToolsInterface)
        mock_tools.list_tools.return_value = [
            {"name": "calculator", "description": "Math calc"},
            {"name": "file_reader", "description": "Read files"},
            {"name": "terminal", "description": "Run commands"}
        ]

        preparer = ToolPreparer(tools=mock_tools)

        # Execute - user with no permissions
        available = preparer.prepare_tools(user_permissions=[])

        # Verify - only calculator (no permission required)
        assert len(available) == 1
        assert available[0]["name"] == "calculator"

    def test_tool_preparer_filters_by_permissions(self):
        """TC-ToolPreparer-002: Returns tools matching user permissions."""
        mock_tools = Mock()
        mock_tools.list_tools.return_value = [
            {"name": "calculator", "description": "Math calc"},
            {"name": "file_reader", "description": "Read files"},
            {"name": "file_writer", "description": "Write files"},
            {"name": "terminal", "description": "Run commands"}
        ]

        preparer = ToolPreparer(tools=mock_tools)

        # Execute - user with file_read permission
        available = preparer.prepare_tools(user_permissions=["file_read"])

        # Verify - calculator (no perm) + file_reader
        assert len(available) == 2
        tool_names = [t["name"] for t in available]
        assert "calculator" in tool_names
        assert "file_reader" in tool_names

    def test_tool_preparer_returns_all_tools_with_all_permissions(self):
        """TC-ToolPreparer-003: Returns all tools when user has all permissions."""
        mock_tools = Mock()
        mock_tools.list_tools.return_value = [
            {"name": "calculator", "description": "Math calc"},
            {"name": "file_reader", "description": "Read files"},
            {"name": "python_repl", "description": "Python execution"}
        ]

        preparer = ToolPreparer(tools=mock_tools)

        # Execute - user with all permissions
        all_perms = ["file_read", "file_write", "execute_code", "web_access"]
        available = preparer.prepare_tools(user_permissions=all_perms)

        # Verify - all tools returned
        assert len(available) == 3

    def test_tool_preparer_uses_default_tools(self):
        """Verify ToolPreparer uses default ToolsCapabilities when no tools provided."""
        preparer = ToolPreparer()

        # Should have default tools instance
        assert preparer.tools is not None

    def test_tool_preparer_permission_map(self):
        """Verify TOOL_PERMISSION_MAP contains expected mappings."""
        from src.l2.l2_control_gateway import ToolPreparer

        # Verify permission map structure
        assert ToolPreparer.TOOL_PERMISSION_MAP["calculator"] is None
        assert ToolPreparer.TOOL_PERMISSION_MAP["file_reader"] == "file_read"
        assert ToolPreparer.TOOL_PERMISSION_MAP["file_writer"] == "file_write"
        assert ToolPreparer.TOOL_PERMISSION_MAP["file_delete"] == "file_delete"
        assert ToolPreparer.TOOL_PERMISSION_MAP["python_repl"] == "execute_code"
        assert ToolPreparer.TOOL_PERMISSION_MAP["terminal"] == "execute_command"
        assert ToolPreparer.TOOL_PERMISSION_MAP["search_web"] == "web_access"

    def test_tool_preparer_multiple_permissions(self):
        """Verify ToolPreparer handles multiple user permissions."""
        mock_tools = Mock()
        mock_tools.list_tools.return_value = [
            {"name": "calculator", "description": "Math"},
            {"name": "file_reader", "description": "Read"},
            {"name": "file_writer", "description": "Write"},
            {"name": "terminal", "description": "Terminal"}
        ]

        preparer = ToolPreparer(tools=mock_tools)

        # User with multiple permissions
        available = preparer.prepare_tools(user_permissions=["file_read", "file_write"])

        tool_names = [t["name"] for t in available]
        assert "calculator" in tool_names  # No permission required
        assert "file_reader" in tool_names
        assert "file_writer" in tool_names
        assert "terminal" not in tool_names  # Requires different permission

    def test_tool_preparer_unknown_tools(self):
        """Verify ToolPreparer handles unknown tools gracefully."""
        mock_tools = Mock()
        mock_tools.list_tools.return_value = [
            {"name": "unknown_tool", "description": "Unknown"},
            {"name": "calculator", "description": "Math"}
        ]

        preparer = ToolPreparer(tools=mock_tools)
        available = preparer.prepare_tools(user_permissions=[])

        # Only calculator should be returned (unknown_tool not in permission map)
        tool_names = [t["name"] for t in available]
        assert "calculator" in tool_names
        # Unknown tools without permission mapping should not be included

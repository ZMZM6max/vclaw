"""Tests for ToolsInterface.

TC-ToolsInterface-001: ToolsInterface can be implemented
"""
import sys
sys.path.insert(0, 'src')

from src.core.interfaces import ToolsInterface


class TestToolsInterface:
    """Tests for ToolsInterface abstract class."""

    def test_tools_interface_can_be_implemented(self):
        """TC-ToolsInterface-001: ToolsInterface can be implemented."""
        class MockTools(ToolsInterface):
            def execute(self, action_name, params, user_permissions, timeout=30):
                return None

            def get_available_tools(self, user_permissions):
                return []

            def list_tools(self):
                return [{"name": "test_tool"}]

        mock = MockTools()
        result = mock.list_tools()

        assert result[0]["name"] == "test_tool"

    def test_tools_interface_requires_execute_method(self):
        """Verify ToolsInterface requires execute method."""
        try:
            class IncompleteTools(ToolsInterface):
                def get_available_tools(self, user_permissions):
                    return []

                def list_tools(self):
                    return []

            # This should raise TypeError because execute is not implemented
            IncompleteTools()
            assert False, "Should have raised TypeError"
        except TypeError as e:
            assert "execute" in str(e)

    def test_tools_interface_requires_list_tools_method(self):
        """Verify ToolsInterface requires list_tools method."""
        try:
            class IncompleteTools(ToolsInterface):
                def execute(self, action_name, params, user_permissions, timeout=30):
                    return None

                def get_available_tools(self, user_permissions):
                    return []

            # This should raise TypeError because list_tools is not implemented
            IncompleteTools()
            assert False, "Should have raised TypeError"
        except TypeError as e:
            assert "list_tools" in str(e)

    def test_mock_tools_returns_expected_format(self):
        """Verify mock implementation returns expected tool format."""
        class MockTools(ToolsInterface):
            def execute(self, action_name, params, user_permissions, timeout=30):
                return None

            def get_available_tools(self, user_permissions):
                return []

            def list_tools(self):
                return [
                    {
                        "name": "calculator",
                        "description": "Math calculator",
                        "parameters": {"expression": {"type": "string"}}
                    }
                ]

        mock = MockTools()
        tools = mock.list_tools()

        assert len(tools) == 1
        assert tools[0]["name"] == "calculator"
        assert "description" in tools[0]
        assert "parameters" in tools[0]

"""Verify src/tools/ advanced tools are not wired into L5 core execution."""
import sys
sys.path.insert(0, 'src')

from unittest.mock import Mock
from src.l5.l5_tools import ToolsCapabilities


class TestNoDualToolSystem:
    """XML-defined tools must be implemented in src/l5/, not delegated to src/tools/."""

    def test_search_web_does_not_use_advanced_tools(self):
        """search_web must use native mock/search implementation, not src/tools/."""
        mock_runtime = Mock()
        tools = ToolsCapabilities(runtime=mock_runtime, enable_permissions=False)
        tools.advanced_tools = Mock()
        tools.advanced_tools.list_tools.return_value = ["web_search"]

        result = tools.execute("search_web", {"query": "test"})

        # Should NOT call advanced_tools even though it advertises web_search
        tools.advanced_tools.call.assert_not_called()
        assert "test" in result.result

    def test_xml_tools_use_native_execution(self):
        """All XML-defined tools must be in ToolRegistry."""
        mock_runtime = Mock()
        tools = ToolsCapabilities(runtime=mock_runtime, enable_permissions=False)

        xml_tools = ["file_read", "file_write", "search_web",
                     "python_repl", "terminal", "calculator", "file_search"]

        for tool_name in xml_tools:
            tool = tools.registry.get(tool_name)
            assert tool is not None, f"Tool '{tool_name}' not found in registry"

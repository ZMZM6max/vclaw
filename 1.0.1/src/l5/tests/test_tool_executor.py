"""Test L5 tool execution delegates to L6 and uses XML-compliant names."""
import sys
sys.path.insert(0, 'src')

import pytest
from unittest.mock import Mock
from src.core.models import Observation, ExecutionResult
from src.l5.l5_tools import ToolRegistry, ToolsCapabilities


class TestToolNames:
    """Verify XML-compliant tool names."""

    def test_file_read_exists(self):
        registry = ToolRegistry()
        assert registry.get("file_read") is not None

    def test_file_write_exists(self):
        registry = ToolRegistry()
        assert registry.get("file_write") is not None

    def test_file_search_exists(self):
        registry = ToolRegistry()
        assert registry.get("file_search") is not None

    def test_old_file_reader_name_removed(self):
        registry = ToolRegistry()
        assert registry.get("file_reader") is None

    def test_old_file_writer_name_removed(self):
        registry = ToolRegistry()
        assert registry.get("file_writer") is None


class TestTerminalDelegatesToL6:
    """Verify terminal tool delegates to RuntimeInterface.run_command."""

    def test_terminal_calls_run_command(self):
        mock_runtime = Mock()
        mock_runtime.run_command.return_value = ExecutionResult(
            exit_code=0,
            stdout="file1.txt\nfile2.txt",
            stderr="",
            execution_time=0.5
        )

        tools = ToolsCapabilities(runtime=mock_runtime, enable_permissions=False)
        result = tools.execute("terminal", {"command": "ls"}, timeout=10)

        assert isinstance(result, Observation)
        assert result.status == "success"
        mock_runtime.run_command.assert_called_once_with("ls", timeout=10)

    def test_terminal_returns_error_on_nonzero_exit(self):
        mock_runtime = Mock()
        mock_runtime.run_command.return_value = ExecutionResult(
            exit_code=1,
            stdout="",
            stderr="Permission denied",
            execution_time=0.1
        )

        tools = ToolsCapabilities(runtime=mock_runtime, enable_permissions=False)
        result = tools.execute("terminal", {"command": "rm protected"}, timeout=10)

        assert result.status == "error"
        assert "权限不足" in result.result or "Permission denied" in result.result

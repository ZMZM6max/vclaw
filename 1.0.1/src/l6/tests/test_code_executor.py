"""Tests for CodeExecutor."""
import pytest
import sys
from unittest.mock import Mock

sys.path.insert(0, 'src')

from src.l6.code_executor import CodeExecutor
from src.core.models import ExecutionResult
from src.core.exceptions import UnsupportedLanguageError


class TestCodeExecutorInit:
    """Tests for CodeExecutor initialization (CE_003)."""

    def test_default_runtime(self):
        """CE_003: Default runtime is RuntimeEnvironment instance."""
        executor = CodeExecutor()
        from src.l6.runtime_environment import RuntimeEnvironment
        assert isinstance(executor.runtime, RuntimeEnvironment)

    def test_injected_runtime(self):
        """Test runtime can be injected via constructor."""
        mock_runtime = Mock()
        executor = CodeExecutor(runtime=mock_runtime)
        assert executor.runtime is mock_runtime


class TestCodeExecutorRun:
    """Tests for CodeExecutor.run method."""

    def test_run_python_success(self):
        """CE_001: Execute Python code successfully via mock runtime."""
        mock_runtime = Mock()
        mock_runtime.run_code.return_value = ExecutionResult(
            exit_code=0,
            stdout="4",
            stderr="",
            execution_time=0.1,
            resource_usage={"memory_peak_mb": 10.0, "cpu_time_ms": 5.0},
        )

        executor = CodeExecutor(runtime=mock_runtime)
        result = executor.run("python", "print(2+2)")

        mock_runtime.run_code.assert_called_once_with(
            "python", "print(2+2)", timeout=30
        )
        assert result.exit_code == 0
        assert result.stdout == "4"

    def test_run_unsupported_language(self):
        """CE_002: Unsupported language raises UnsupportedLanguageError."""
        executor = CodeExecutor()
        with pytest.raises(UnsupportedLanguageError):
            executor.run("ruby", "puts 1")

    def test_timeout_passed(self):
        """CE_004: Timeout parameter is forwarded to runtime."""
        mock_runtime = Mock()
        mock_runtime.run_code.return_value = ExecutionResult(
            exit_code=0,
            stdout="hello",
            stderr="",
            execution_time=0.1,
            resource_usage={},
        )

        executor = CodeExecutor(runtime=mock_runtime)
        executor.run("bash", "echo hello", timeout=10)

        mock_runtime.run_code.assert_called_once_with(
            "bash", "echo hello", timeout=10
        )

    def test_language_case_insensitive(self):
        """Test language validation is case insensitive and strips whitespace."""
        mock_runtime = Mock()
        mock_runtime.run_code.return_value = ExecutionResult(
            exit_code=0,
            stdout="",
            stderr="",
            execution_time=0.1,
            resource_usage={},
        )

        executor = CodeExecutor(runtime=mock_runtime)

        executor.run("PYTHON", "print(1)")
        mock_runtime.run_code.assert_called_with(
            "python", "print(1)", timeout=30
        )

        executor.run("  JavaScript  ", "console.log(1)")
        mock_runtime.run_code.assert_called_with(
            "javascript", "console.log(1)", timeout=30
        )

    def test_run_javascript(self):
        """Test JavaScript execution delegation."""
        mock_runtime = Mock()
        mock_runtime.run_code.return_value = ExecutionResult(
            exit_code=0,
            stdout="JS output",
            stderr="",
            execution_time=0.1,
            resource_usage={},
        )

        executor = CodeExecutor(runtime=mock_runtime)
        result = executor.run("javascript", "console.log('JS')")

        assert result.stdout == "JS output"
        mock_runtime.run_code.assert_called_once_with(
            "javascript", "console.log('JS')", timeout=30
        )

    def test_run_bash(self):
        """Test Bash execution delegation."""
        mock_runtime = Mock()
        mock_runtime.run_code.return_value = ExecutionResult(
            exit_code=0,
            stdout="Bash output",
            stderr="",
            execution_time=0.1,
            resource_usage={},
        )

        executor = CodeExecutor(runtime=mock_runtime)
        result = executor.run("bash", "echo 'Bash'")

        assert result.stdout == "Bash output"
        mock_runtime.run_code.assert_called_once_with(
            "bash", "echo 'Bash'", timeout=30
        )

    def test_result_passed_through_unchanged(self):
        """Test ExecutionResult is returned unchanged without modification."""
        mock_runtime = Mock()
        expected_result = ExecutionResult(
            exit_code=1,
            stdout="",
            stderr="error",
            execution_time=0.5,
            resource_usage={"memory_peak_mb": 100.0},
        )
        mock_runtime.run_code.return_value = expected_result

        executor = CodeExecutor(runtime=mock_runtime)
        result = executor.run("python", "bad code")

        assert result is expected_result

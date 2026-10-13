"""Tests for L6 Runtime Environment."""
import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import sys
sys.path.insert(0, 'src')

from src.l6.l6_runtime import RuntimeEnvironment
from src.l6.config import SandboxConfig
from src.core.models import ExecutionResult
from src.core.exceptions import (
    UnsupportedLanguageError,
    SecurityViolationError,
    ExecutionTimeoutError
)


class TestRuntimeEnvironmentInit:
    """Tests for RuntimeEnvironment initialization."""

    def test_init_with_default_config(self):
        """Test initialization with default config."""
        runtime = RuntimeEnvironment()
        assert runtime.config is not None
        assert isinstance(runtime.config, SandboxConfig)

    def test_init_with_custom_config(self):
        """Test initialization with custom config."""
        config = SandboxConfig(memory_limit=1024, timeout=60)
        runtime = RuntimeEnvironment(config)
        assert runtime.config.memory_limit == 1024
        assert runtime.config.timeout == 60


class TestRuntimeEnvironmentRunCode:
    """Tests for run_code method."""

    @patch('src.l6.l6_runtime.DockerSandbox')
    def test_run_python_success(self, mock_sandbox_class):
        """Test successful Python execution."""
        # Setup mocks
        mock_sandbox = MagicMock()
        mock_sandbox.create.return_value = "env123"
        mock_sandbox.execute.return_value = ExecutionResult(
            exit_code=0,
            stdout="Hello World",
            stderr="",
            execution_time=0.5
        )
        mock_sandbox_class.return_value = mock_sandbox

        # Test
        runtime = RuntimeEnvironment()
        result = runtime.run_code("python", "print('Hello World')")

        # Verify
        assert isinstance(result, ExecutionResult)
        assert result.exit_code == 0
        assert result.stdout == "Hello World"
        mock_sandbox.create.assert_called_once()
        mock_sandbox.execute.assert_called_once()
        mock_sandbox.destroy.assert_called_once_with("env123")

    def test_run_unsupported_language(self):
        """Test unsupported language raises error."""
        runtime = RuntimeEnvironment()

        with pytest.raises(UnsupportedLanguageError):
            runtime.run_code("ruby", "puts 'Hello'")

    def test_run_forbidden_code(self):
        """Test forbidden code raises security error."""
        runtime = RuntimeEnvironment()

        with pytest.raises(SecurityViolationError):
            runtime.run_code("python", "import os; os.system('ls')")

    @patch('src.l6.l6_runtime.DockerSandbox')
    def test_cleanup_on_error(self, mock_sandbox_class):
        """Test cleanup happens even on error."""
        mock_sandbox = MagicMock()
        mock_sandbox.create.return_value = "env456"
        mock_sandbox.execute.side_effect = Exception("Execution failed")
        mock_sandbox_class.return_value = mock_sandbox

        runtime = RuntimeEnvironment()

        with pytest.raises(Exception):
            runtime.run_code("python", "print('test')")

        # Cleanup should still be called
        mock_sandbox.destroy.assert_called_once_with("env456")


class TestRuntimeEnvironmentLanguages:
    """Tests for different language support."""

    @patch('src.l6.l6_runtime.DockerSandbox')
    def test_run_javascript(self, mock_sandbox_class):
        """Test JavaScript execution."""
        mock_sandbox = MagicMock()
        mock_sandbox.create.return_value = "env_js"
        mock_sandbox.execute.return_value = ExecutionResult(
            exit_code=0,
            stdout="JS output",
            stderr="",
            execution_time=0.3
        )
        mock_sandbox_class.return_value = mock_sandbox

        runtime = RuntimeEnvironment()
        result = runtime.run_code("javascript", "console.log('test')")

        assert result.exit_code == 0
        assert result.stdout == "JS output"

    @patch('src.l6.l6_runtime.DockerSandbox')
    def test_run_bash(self, mock_sandbox_class):
        """Test Bash execution."""
        mock_sandbox = MagicMock()
        mock_sandbox.create.return_value = "env_bash"
        mock_sandbox.execute.return_value = ExecutionResult(
            exit_code=0,
            stdout="Bash output",
            stderr="",
            execution_time=0.1
        )
        mock_sandbox_class.return_value = mock_sandbox

        runtime = RuntimeEnvironment()
        result = runtime.run_code("bash", "echo 'test'")

        assert result.exit_code == 0
        assert result.stdout == "Bash output"


class TestRuntimeEnvironmentSecurity:
    """Tests for security features."""

    def test_code_size_limit(self):
        """Test code size limit is enforced."""
        runtime = RuntimeEnvironment()
        large_code = "x = 1\n" * 20000  # > 100KB

        with pytest.raises(SecurityViolationError) as exc_info:
            runtime.run_code("python", large_code)

        assert "size" in str(exc_info.value).lower()

    def test_eval_blocked(self):
        """Test eval() is blocked."""
        runtime = RuntimeEnvironment()

        with pytest.raises(SecurityViolationError):
            runtime.run_code("python", "eval('1 + 1')")

    def test_exec_blocked(self):
        """Test exec() is blocked."""
        runtime = RuntimeEnvironment()

        with pytest.raises(SecurityViolationError):
            runtime.run_code("python", "exec('print(1)')")

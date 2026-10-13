"""Tests for DockerSandbox."""
import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import sys
sys.path.insert(0, 'src')

from src.l6.docker_sandbox import DockerSandbox
from src.l6.config import SandboxConfig
from src.core.models import ExecutionResult


class TestDockerSandboxInit:
    """Tests for DockerSandbox initialization."""

    def test_init_with_default_config(self):
        """Test initialization with default config."""
        import tempfile
        config = SandboxConfig()
        sandbox = DockerSandbox(config)
        assert sandbox.config == config
        # Use cross-platform temp directory
        expected_base_dir = Path(tempfile.gettempdir()) / "vclaw_sandbox"
        assert sandbox.base_dir == expected_base_dir
        assert sandbox._environments == {}

    def test_init_creates_base_dir(self, tmp_path):
        """Test initialization creates base directory."""
        config = SandboxConfig()
        sandbox = DockerSandbox(config)
        assert sandbox.base_dir.exists()


class TestDockerSandboxCreate:
    """Tests for sandbox creation."""

    def test_create_generates_id(self):
        """Test create generates environment ID."""
        config = SandboxConfig()
        sandbox = DockerSandbox(config)

        env_id = sandbox.create()

        assert env_id.startswith("env_")
        assert len(env_id) == 12  # env_ + 8 chars
        assert env_id in sandbox._environments

    def test_create_with_custom_id(self):
        """Test create with custom environment ID."""
        config = SandboxConfig()
        sandbox = DockerSandbox(config)

        env_id = sandbox.create("my_custom_id")

        assert env_id == "my_custom_id"
        assert env_id in sandbox._environments

    def test_create_creates_directory(self, tmp_path):
        """Test create creates environment directory."""
        config = SandboxConfig()
        sandbox = DockerSandbox(config)
        sandbox.base_dir = tmp_path / "sandbox"

        env_id = sandbox.create("test_env")

        assert (sandbox.base_dir / "test_env").exists()


class TestDockerSandboxExecute:
    """Tests for code execution."""

    @patch('src.l6.docker_sandbox.DockerController')
    def test_execute_python(self, mock_controller_class):
        """Test executing Python code."""
        # Setup mocks
        mock_controller = MagicMock()
        mock_controller.create_container.return_value = "container123"
        mock_controller.exec_in_container.return_value = (0, "Hello", "")
        mock_controller.get_container_stats.return_value = {
            "memory_peak_mb": 0.0, "cpu_time_ms": 0.0
        }
        mock_controller_class.return_value = mock_controller

        # Create sandbox
        config = SandboxConfig()
        sandbox = DockerSandbox(config)
        sandbox.base_dir = Path("/tmp")

        # Create environment and write code
        env_id = sandbox.create()

        # Execute
        result = sandbox.execute(env_id, "python", "print('Hello')")

        # Verify
        assert isinstance(result, ExecutionResult)
        assert result.exit_code == 0
        assert result.stdout == "Hello"
        mock_controller.create_container.assert_called_once()
        mock_controller.exec_in_container.assert_called_once_with(
            "container123",
            ["python", "/sandbox/script.py"],
            timeout=30
        )

    @patch('src.l6.docker_sandbox.DockerController')
    def test_execute_javascript(self, mock_controller_class):
        """Test executing JavaScript code."""
        mock_controller = MagicMock()
        mock_controller.create_container.return_value = "container456"
        mock_controller.exec_in_container.return_value = (0, "Hello JS", "")
        mock_controller.get_container_stats.return_value = {
            "memory_peak_mb": 0.0, "cpu_time_ms": 0.0
        }
        mock_controller_class.return_value = mock_controller

        config = SandboxConfig()
        sandbox = DockerSandbox(config)
        sandbox.base_dir = Path("/tmp")

        env_id = sandbox.create()
        result = sandbox.execute(env_id, "javascript", "console.log('Hello')")

        assert result.exit_code == 0
        mock_controller.exec_in_container.assert_called_once_with(
            "container456",
            ["node", "/sandbox/script.js"],
            timeout=30
        )

    @patch('src.l6.docker_sandbox.DockerController')
    def test_execute_error(self, mock_controller_class):
        """Test execution with error."""
        mock_controller = MagicMock()
        mock_controller.create_container.return_value = "container789"
        mock_controller.exec_in_container.return_value = (1, "", "Error")
        mock_controller.get_container_stats.return_value = {
            "memory_peak_mb": 0.0, "cpu_time_ms": 0.0
        }
        mock_controller_class.return_value = mock_controller

        config = SandboxConfig()
        sandbox = DockerSandbox(config)
        sandbox.base_dir = Path("/tmp")

        env_id = sandbox.create()
        result = sandbox.execute(env_id, "python", "invalid syntax")

        assert result.exit_code == 1
        assert "Error" in result.stderr


class TestDockerSandboxDestroy:
    """Tests for sandbox destruction."""

    def test_destroy_removes_environment(self):
        """Test destroy removes environment."""
        config = SandboxConfig()
        sandbox = DockerSandbox(config)
        sandbox.base_dir = Path("/tmp")

        env_id = sandbox.create("test_env")
        result = sandbox.destroy(env_id)

        assert result is True
        assert env_id not in sandbox._environments

    def test_destroy_nonexistent_returns_false(self):
        """Test destroy non-existent environment returns False."""
        config = SandboxConfig()
        sandbox = DockerSandbox(config)

        result = sandbox.destroy("nonexistent")

        assert result is False

    @patch('src.l6.docker_sandbox.DockerController')
    def test_destroy_removes_container(self, mock_controller_class):
        """Test destroy removes Docker container."""
        mock_controller = MagicMock()
        mock_controller_class.return_value = mock_controller

        config = SandboxConfig()
        sandbox = DockerSandbox(config)
        sandbox.base_dir = Path("/tmp")

        env_id = sandbox.create("test_env")
        sandbox._environments[env_id]["container_id"] = "container123"

        sandbox.destroy(env_id)

        mock_controller.remove_container.assert_called_once_with(
            "container123", force=True
        )

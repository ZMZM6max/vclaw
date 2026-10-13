"""Tests for SandboxManager."""
import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, 'src')

import pytest

from src.l6.sandbox_manager import SandboxManager
from src.l6.config import SandboxConfig
from src.core.models import ExecutionResult
from src.core.exceptions import SandboxCreationError


class TestSandboxManagerInit:
    """Tests for SandboxManager initialization."""

    def test_default_base_dir(self):
        """Test default base directory uses system temp."""
        import tempfile
        manager = SandboxManager()
        expected = Path(tempfile.gettempdir()) / "vclaw_sandbox"
        assert manager.base_dir == expected

    def test_custom_base_dir(self):
        """Test custom base directory."""
        manager = SandboxManager(base_dir="/tmp/custom_sandbox")
        assert manager.base_dir == Path("/tmp/custom_sandbox")

    def test_environments_dict_empty(self):
        """Test environments dict starts empty."""
        manager = SandboxManager()
        assert manager._environments == {}


class TestSandboxManagerCreate:
    """Tests for create method."""

    def test_create_generates_id(self):
        """Test create generates environment ID."""
        manager = SandboxManager()
        env_id = manager.create()

        assert env_id.startswith("env_")
        assert len(env_id) == 12  # env_ + 8 chars
        assert env_id in manager._environments

    def test_create_with_custom_id(self):
        """Test create with custom environment ID."""
        manager = SandboxManager()
        env_id = manager.create("my_custom_id")

        assert env_id == "my_custom_id"
        assert env_id in manager._environments

    def test_create_creates_directory(self, tmp_path):
        """Test create creates environment directory."""
        manager = SandboxManager(base_dir=str(tmp_path))
        env_id = manager.create("test_env")

        assert (manager.base_dir / "test_env").exists()

    def test_create_stores_config(self):
        """Test create stores config in environment info."""
        manager = SandboxManager()
        config = SandboxConfig(memory_limit=1024)
        env_id = manager.create(config=config)

        assert manager._environments[env_id]["config"] == config


class TestSandboxManagerExecute:
    """Tests for execute method."""

    def test_execute_python(self):
        """Test executing Python code."""
        manager = SandboxManager()
        manager._controller = MagicMock()
        manager._controller.create_container.return_value = "container123"
        manager._controller.exec_in_container.return_value = (0, "Hello", "")
        manager._controller.get_container_stats.return_value = {
            "memory_peak_mb": 0.0, "cpu_time_ms": 0.0
        }

        manager.base_dir = Path("/tmp")
        env_id = manager.create()

        result = manager.execute(env_id, "python", "print('Hello')")

        assert isinstance(result, ExecutionResult)
        assert result.exit_code == 0
        assert result.stdout == "Hello"
        manager._controller.create_container.assert_called_once()
        manager._controller.exec_in_container.assert_called_once_with(
            "container123",
            ["python", "/sandbox/script.py"],
            timeout=30,
        )

    def test_execute_javascript(self):
        """Test executing JavaScript code."""
        manager = SandboxManager()
        manager._controller = MagicMock()
        manager._controller.create_container.return_value = "container456"
        manager._controller.exec_in_container.return_value = (0, "Hello JS", "")
        manager._controller.get_container_stats.return_value = {
            "memory_peak_mb": 0.0, "cpu_time_ms": 0.0
        }

        manager.base_dir = Path("/tmp")
        env_id = manager.create()

        result = manager.execute(env_id, "javascript", "console.log('Hello')")

        assert result.exit_code == 0
        assert result.stdout == "Hello JS"
        manager._controller.exec_in_container.assert_called_once_with(
            "container456",
            ["node", "/sandbox/script.js"],
            timeout=30,
        )

    def test_execute_bash(self):
        """Test executing Bash code."""
        manager = SandboxManager()
        manager._controller = MagicMock()
        manager._controller.create_container.return_value = "container789"
        manager._controller.exec_in_container.return_value = (0, "Hello Bash", "")
        manager._controller.get_container_stats.return_value = {
            "memory_peak_mb": 0.0, "cpu_time_ms": 0.0
        }

        manager.base_dir = Path("/tmp")
        env_id = manager.create()

        result = manager.execute(env_id, "bash", "echo 'Hello'")

        assert result.exit_code == 0
        assert result.stdout == "Hello Bash"
        manager._controller.exec_in_container.assert_called_once_with(
            "container789",
            ["bash", "/sandbox/script.sh"],
            timeout=30,
        )

    def test_execute_error(self):
        """Test execution with error."""
        manager = SandboxManager()
        manager._controller = MagicMock()
        manager._controller.create_container.return_value = "container789"
        manager._controller.exec_in_container.return_value = (1, "", "Error")
        manager._controller.get_container_stats.return_value = {
            "memory_peak_mb": 0.0, "cpu_time_ms": 0.0
        }

        manager.base_dir = Path("/tmp")
        env_id = manager.create()

        result = manager.execute(env_id, "python", "invalid syntax")

        assert result.exit_code == 1
        assert "Error" in result.stderr

    def test_execute_custom_timeout(self):
        """Test execute with custom timeout."""
        manager = SandboxManager()
        manager._controller = MagicMock()
        manager._controller.create_container.return_value = "container123"
        manager._controller.exec_in_container.return_value = (0, "", "")
        manager._controller.get_container_stats.return_value = {
            "memory_peak_mb": 0.0, "cpu_time_ms": 0.0
        }

        manager.base_dir = Path("/tmp")
        env_id = manager.create()

        manager.execute(env_id, "python", "print(1)", timeout=60)

        manager._controller.exec_in_container.assert_called_once_with(
            "container123",
            ["python", "/sandbox/script.py"],
            timeout=60,
        )

    def test_execute_resource_usage_populated(self):
        """Test ExecutionResult contains resource_usage keys."""
        manager = SandboxManager()
        manager._controller = MagicMock()
        manager._controller.create_container.return_value = "container123"
        manager._controller.exec_in_container.return_value = (0, "hello", "")
        manager._controller.get_container_stats.return_value = {
            "memory_peak_mb": 64.0, "cpu_time_ms": 12.0
        }

        manager.base_dir = Path("/tmp")
        env_id = manager.create()

        result = manager.execute(env_id, "python", "print('hello')")

        assert "memory_peak_mb" in result.resource_usage
        assert "cpu_time_ms" in result.resource_usage
        assert result.resource_usage["memory_peak_mb"] == 64.0
        assert result.resource_usage["cpu_time_ms"] == 12.0

    def test_execute_nonexistent_environment(self):
        """Test execute with non-existent environment raises ValueError."""
        manager = SandboxManager()

        with pytest.raises(ValueError, match="nonexistent"):
            manager.execute("nonexistent", "python", "print(1)")

    def test_execute_container_creation_failure(self):
        """Test execute raises SandboxCreationError when container creation fails."""
        manager = SandboxManager()
        manager._controller = MagicMock()
        manager._controller.create_container.side_effect = Exception("Docker error")

        manager.base_dir = Path("/tmp")
        env_id = manager.create()

        with pytest.raises(SandboxCreationError):
            manager.execute(env_id, "python", "print(1)")

    def test_execute_saves_container_id(self):
        """Test container ID is saved to environment info."""
        manager = SandboxManager()
        manager._controller = MagicMock()
        manager._controller.create_container.return_value = "container123"
        manager._controller.exec_in_container.return_value = (0, "", "")
        manager._controller.get_container_stats.return_value = {
            "memory_peak_mb": 0.0, "cpu_time_ms": 0.0
        }

        manager.base_dir = Path("/tmp")
        env_id = manager.create()

        manager.execute(env_id, "python", "print(1)")

        assert manager._environments[env_id]["container_id"] == "container123"

    def test_execute_with_config(self):
        """Test execute passes config values to DockerController."""
        manager = SandboxManager()
        manager._controller = MagicMock()
        manager._controller.create_container.return_value = "container123"
        manager._controller.exec_in_container.return_value = (0, "", "")
        manager._controller.get_container_stats.return_value = {
            "memory_peak_mb": 0.0, "cpu_time_ms": 0.0
        }

        manager.base_dir = Path("/tmp")
        config = SandboxConfig(memory_limit=1024, cpu_limit=2.0, enable_network=True)
        env_id = manager.create(config=config)

        manager.execute(env_id, "python", "print(1)")

        call_kwargs = manager._controller.create_container.call_args[1]
        assert call_kwargs["mem_limit"] == "1024m"
        assert call_kwargs["cpu_quota"] == 200000
        assert call_kwargs["network_mode"] == "bridge"


class TestSandboxManagerDestroy:
    """Tests for destroy method."""

    def test_destroy_removes_environment(self, tmp_path):
        """Test destroy removes environment."""
        manager = SandboxManager(base_dir=str(tmp_path))
        env_id = manager.create("test_env")

        result = manager.destroy(env_id)

        assert result is True
        assert env_id not in manager._environments

    def test_destroy_nonexistent_returns_false(self):
        """Test destroy non-existent environment returns False."""
        manager = SandboxManager()

        result = manager.destroy("nonexistent")

        assert result is False

    def test_destroy_idempotent(self, tmp_path):
        """Test repeated destroy returns False."""
        manager = SandboxManager(base_dir=str(tmp_path))
        env_id = manager.create("test_env")

        manager.destroy(env_id)
        result = manager.destroy(env_id)

        assert result is False

    def test_destroy_removes_container(self):
        """Test destroy removes Docker container."""
        manager = SandboxManager()
        manager._controller = MagicMock()
        manager.base_dir = Path("/tmp")
        env_id = manager.create("test_env")
        manager._environments[env_id]["container_id"] = "container123"

        manager.destroy(env_id)

        manager._controller.remove_container.assert_called_once_with(
            "container123", force=True
        )

    def test_destroy_cleans_directory(self, tmp_path):
        """Test destroy removes the environment directory."""
        manager = SandboxManager(base_dir=str(tmp_path))
        env_id = manager.create("test_env")
        env_path = manager.base_dir / "test_env"

        assert env_path.exists()
        manager.destroy(env_id)
        assert not env_path.exists()

    def test_destroy_no_exception_on_failure(self):
        """Test destroy does not raise on cleanup failure."""
        manager = SandboxManager()
        manager._controller = MagicMock()
        manager.base_dir = Path("/tmp")
        env_id = manager.create("test_env")
        manager._environments[env_id]["container_id"] = "container123"
        manager._controller.remove_container.return_value = False

        result = manager.destroy(env_id)

        assert result is False  # container removal failed

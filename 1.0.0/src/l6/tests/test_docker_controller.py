"""Tests for DockerController."""
import pytest
from unittest.mock import Mock, patch, MagicMock
import sys
sys.path.insert(0, 'src')

from src.l6.docker_controller import DockerController
from src.core.exceptions import SandboxCreationError


class TestDockerControllerInit:
    """Tests for DockerController initialization."""

    def test_lazy_client_initialization(self):
        """Test Docker client is initialized lazily."""
        controller = DockerController()
        assert controller._client is None


class TestDockerControllerCreateContainer:
    """Tests for container creation."""

    @patch('docker.from_env')
    def test_create_python_container(self, mock_from_env):
        """Test creating Python container."""
        # Setup mock
        mock_client = MagicMock()
        mock_container = MagicMock()
        mock_container.id = "abc123"
        mock_client.containers.create.return_value = mock_container
        mock_client.images.get.side_effect = Exception("Not found")
        mock_from_env.return_value = mock_client

        # Test
        controller = DockerController()
        container_id = controller.create_container(
            language="python",
            volumes={"/tmp/test": {"bind": "/sandbox", "mode": "ro"}}
        )

        assert container_id == "abc123"
        mock_client.containers.create.assert_called_once()
        call_kwargs = mock_client.containers.create.call_args[1]
        assert call_kwargs["image"] == "python:3.11-alpine"
        assert call_kwargs["mem_limit"] == "512m"
        assert call_kwargs["network_mode"] == "none"

    @patch('docker.from_env')
    def test_create_javascript_container(self, mock_from_env):
        """Test creating JavaScript container."""
        mock_client = MagicMock()
        mock_container = MagicMock()
        mock_container.id = "def456"
        mock_client.containers.create.return_value = mock_container
        mock_client.images.get.side_effect = Exception("Not found")
        mock_from_env.return_value = mock_client

        controller = DockerController()
        container_id = controller.create_container(
            language="javascript",
            volumes={"/tmp/test": {"bind": "/sandbox", "mode": "ro"}}
        )

        assert container_id == "def456"
        call_kwargs = mock_client.containers.create.call_args[1]
        assert call_kwargs["image"] == "node:18-alpine"

    @patch('docker.from_env')
    def test_create_container_failure(self, mock_from_env):
        """Test container creation failure."""
        mock_client = MagicMock()
        mock_client.containers.create.side_effect = Exception("Docker error")
        mock_client.images.get.side_effect = Exception("Not found")
        mock_from_env.return_value = mock_client

        controller = DockerController()
        with pytest.raises(SandboxCreationError):
            controller.create_container(
                language="python",
                volumes={}
            )


class TestDockerControllerExec:
    """Tests for command execution."""

    @patch('docker.from_env')
    def test_exec_success(self, mock_from_env):
        """Test successful command execution."""
        # Setup mock
        mock_client = MagicMock()
        mock_container = MagicMock()
        mock_result = MagicMock()
        mock_result.exit_code = 0
        mock_result.output = b"Hello World"
        mock_container.exec_run.return_value = mock_result
        mock_client.containers.get.return_value = mock_container
        mock_from_env.return_value = mock_client

        # Test
        controller = DockerController()
        exit_code, stdout, stderr = controller.exec_in_container(
            "abc123",
            ["python", "script.py"]
        )

        assert exit_code == 0
        assert stdout == "Hello World"

    @patch('docker.from_env')
    def test_exec_error(self, mock_from_env):
        """Test command execution with error."""
        mock_client = MagicMock()
        mock_container = MagicMock()
        mock_result = MagicMock()
        mock_result.exit_code = 1
        mock_result.output = b"Error message"
        mock_container.exec_run.return_value = mock_result
        mock_client.containers.get.return_value = mock_container
        mock_from_env.return_value = mock_client

        controller = DockerController()
        exit_code, stdout, stderr = controller.exec_in_container(
            "abc123",
            ["python", "script.py"]
        )

        assert exit_code == 1
        assert "Error" in stdout


class TestDockerControllerRemove:
    """Tests for container removal."""

    @patch('docker.from_env')
    def test_remove_success(self, mock_from_env):
        """Test successful container removal."""
        mock_client = MagicMock()
        mock_container = MagicMock()
        mock_client.containers.get.return_value = mock_container
        mock_from_env.return_value = mock_client

        controller = DockerController()
        result = controller.remove_container("abc123")

        assert result is True
        mock_container.remove.assert_called_once_with(force=True)

    @patch('docker.from_env')
    def test_remove_failure(self, mock_from_env):
        """Test container removal failure."""
        mock_client = MagicMock()
        mock_client.containers.get.side_effect = Exception("Not found")
        mock_from_env.return_value = mock_client

        controller = DockerController()
        result = controller.remove_container("abc123")

        assert result is False

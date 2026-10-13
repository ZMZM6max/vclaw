"""Docker controller for container lifecycle management."""
import time
from typing import List, Dict, Tuple, Optional
from pathlib import Path
from src.core.exceptions import SandboxCreationError


class DockerController:
    """Low-level Docker container controller.

    Wraps docker-py client for container creation, execution, and cleanup.
    """

    # Docker images for each language
    IMAGES = {
        "python": "python:3.11-alpine",
        "javascript": "node:18-alpine",
        "bash": "alpine:latest"
    }

    def __init__(self):
        """Initialize Docker controller."""
        self._client = None

    def _get_client(self):
        """Lazy initialization of Docker client."""
        if self._client is None:
            try:
                import docker
                self._client = docker.from_env()
            except ImportError:
                raise SandboxCreationError(
                    "Docker SDK not installed. Run: pip install docker"
                )
            except Exception as e:
                raise SandboxCreationError(f"Failed to connect to Docker: {e}")
        return self._client

    def create_container(
        self,
        language: str,
        volumes: Dict[str, Dict],
        mem_limit: str = "512m",
        cpu_quota: int = 100000,
        network_mode: str = "none"
    ) -> str:
        """Create a Docker container for code execution.

        Args:
            language: Programming language (determines image)
            volumes: Volume mounts {host_path: {"bind": container_path, "mode": "ro"}}
            mem_limit: Memory limit (e.g., "512m")
            cpu_quota: CPU quota in microseconds (100000 = 1 core)
            network_mode: Network mode ("none" for isolation)

        Returns:
            Container ID string

        Raises:
            SandboxCreationError: If container creation fails
        """
        client = self._get_client()
        image = self.IMAGES.get(language)

        if not image:
            raise SandboxCreationError(f"No Docker image for language: {language}")

        try:
            # Ensure image exists
            try:
                client.images.get(image)
            except:
                # Pull image if not present
                client.images.pull(image)

            # Create container
            container = client.containers.create(
                image=image,
                command=["sleep", "3600"],  # Keep container alive
                volumes=volumes,
                mem_limit=mem_limit,
                cpu_quota=cpu_quota,
                network_mode=network_mode,
                read_only=True,
                detach=True
            )

            # Start container
            container.start()

            return container.id

        except Exception as e:
            raise SandboxCreationError(f"Failed to create container: {e}")

    def exec_in_container(
        self,
        container_id: str,
        command: List[str],
        timeout: int = 30
    ) -> Tuple[int, str, str]:
        """Execute a command in a running container.

        Args:
            container_id: Docker container ID
            command: Command and arguments as list
            timeout: Timeout in seconds

        Returns:
            Tuple of (exit_code, stdout, stderr)
        """
        client = self._get_client()

        try:
            container = client.containers.get(container_id)

            # Execute command
            result = container.exec_run(
                cmd=command,
                stdout=True,
                stderr=True,
                stdin=False,
                tty=False
            )

            # Decode output
            stdout = result.output.decode('utf-8', errors='replace') if result.output else ""
            stderr = ""  # exec_run combines stdout/stderr in output

            # Truncate if too long
            if len(stdout) > 10000:
                stdout = stdout[:9970] + "\n[Output truncated...]"

            return result.exit_code, stdout, stderr

        except Exception as e:
            return 1, "", str(e)

    def remove_container(self, container_id: str, force: bool = True) -> bool:
        """Remove a Docker container.

        Args:
            container_id: Container ID to remove
            force: Whether to force remove running containers

        Returns:
            True if removed successfully, False otherwise
        """
        client = self._get_client()

        try:
            container = client.containers.get(container_id)
            container.remove(force=force)
            return True
        except Exception:
            return False

    def is_container_running(self, container_id: str) -> bool:
        """Check if a container is running.

        Args:
            container_id: Container ID to check

        Returns:
            True if running, False otherwise
        """
        client = self._get_client()

        try:
            container = client.containers.get(container_id)
            return container.status == "running"
        except Exception:
            return False

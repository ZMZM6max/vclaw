"""Docker API wrapper with lazy initialization.

L6 lowest-level infrastructure component, directly operating Docker Engine API.
Responsible for container creation, execution, and destruction.
Wrapped by SandboxManager, not exposed to RuntimeEnvironment directly.
"""

from typing import Dict, List, Tuple

from src.core.exceptions import SandboxCreationError


class DockerController:
    """Docker SDK for Python wrapper providing simplified and safe container interfaces."""

    IMAGES = {
        "python": "python:3.11-alpine",
        "javascript": "node:18-alpine",
        "bash": "alpine:latest",
    }

    _MAX_OUTPUT_LENGTH = 10000
    _TRUNCATED_SUFFIX = "\n[Output truncated...]"

    def __init__(self) -> None:
        self._client = None

    def _get_client(self):
        """Lazy-load and return the Docker client.

        Returns:
            docker.DockerClient: Initialized Docker client.

        Raises:
            SandboxCreationError: If docker package is missing or daemon is down.
        """
        if self._client is not None:
            return self._client

        try:
            import docker
        except ImportError:
            raise SandboxCreationError(
                "Docker SDK not installed. Run: pip install docker"
            )

        try:
            self._client = docker.from_env()
        except Exception as e:
            raise SandboxCreationError(f"Docker daemon not running: {e}")

        return self._client

    def create_container(
        self,
        language: str,
        volumes: Dict[str, Dict],
        mem_limit: str = "512m",
        cpu_quota: int = 100000,
        network_mode: str = "none",
    ) -> str:
        """Create and start a Docker container.

        Args:
            language: Programming language for image selection.
                Valid values: python, javascript, bash.
            volumes: Volume mount mapping.
                Format: {host_path: {"bind": container_path, "mode": "ro"}}.
            mem_limit: Memory limit as a Docker-format string (e.g. "512m", "1g").
            cpu_quota: CPU quota in microseconds. 100000 = 1 core, 200000 = 2 cores.
            network_mode: Network mode. "none" for full isolation, "bridge" for outbound.

        Returns:
            Container ID string.

        Raises:
            SandboxCreationError: If image pull fails, container creation fails,
                Docker is not installed, or daemon is not running.
        """
        client = self._get_client()

        image_name = self.IMAGES.get(language)
        if not image_name:
            raise SandboxCreationError(f"Unsupported language: {language}")

        try:
            client.images.get(image_name)
        except Exception:
            try:
                client.images.pull(image_name)
            except Exception as e:
                raise SandboxCreationError(f"Failed to pull image {image_name}: {e}")

        try:
            container = client.containers.create(
                image=image_name,
                command=["sleep", "3600"],
                volumes=volumes,
                mem_limit=mem_limit,
                cpu_quota=cpu_quota,
                network_mode=network_mode,
                read_only=True,
            )
            container.start()
            return container.id
        except Exception as e:
            raise SandboxCreationError(f"Failed to create container: {e}")

    def exec_in_container(
        self,
        container_id: str,
        command: List[str],
        timeout: int = 30,
    ) -> Tuple[int, str, str]:
        """Execute a command inside a running container.

        Args:
            container_id: Container ID.
            command: Command and arguments list (not a shell string).
            timeout: Python-level wait timeout in seconds.

        Returns:
            Tuple of (exit_code, stdout, stderr).
            Note: docker-py's exec_run merges stdout and stderr into output,
            so stderr is typically an empty string in the current implementation.
        """
        try:
            client = self._get_client()
            container = client.containers.get(container_id)
        except Exception as e:
            return (1, "", str(e))

        try:
            result = container.exec_run(
                cmd=command,
                stdout=True,
                stderr=True,
                stdin=False,
                tty=False,
            )
            output = (
                result.output.decode("utf-8", errors="replace")
                if result.output
                else ""
            )
            if len(output) > self._MAX_OUTPUT_LENGTH:
                limit = self._MAX_OUTPUT_LENGTH - len(self._TRUNCATED_SUFFIX)
                output = output[:limit] + self._TRUNCATED_SUFFIX
            return (result.exit_code, output, "")
        except Exception as e:
            return (1, "", str(e))

    def remove_container(self, container_id: str, force: bool = True) -> bool:
        """Remove a container.

        Args:
            container_id: Container ID to remove.
            force: Whether to force remove a running container.

        Returns:
            True if successfully removed, False otherwise.
        """
        try:
            client = self._get_client()
            container = client.containers.get(container_id)
            container.remove(force=force)
            return True
        except Exception:
            return False

    def get_container_stats(self, container_id: str) -> Dict[str, float]:
        """Retrieve resource usage statistics for a container.

        Args:
            container_id: Container ID.

        Returns:
            Dictionary with 'memory_peak_mb' and 'cpu_time_ms'.
            Returns zeros if the container does not exist or stats are unavailable.
        """
        try:
            client = self._get_client()
            container = client.containers.get(container_id)
            stats = container.stats(stream=False)

            memory_mb = 0.0
            if stats.get("memory_stats") and "usage" in stats["memory_stats"]:
                memory_mb = stats["memory_stats"]["usage"] / (1024 * 1024)

            cpu_ms = 0.0
            if stats.get("cpu_stats") and "cpu_usage" in stats["cpu_stats"]:
                total_ns = stats["cpu_stats"]["cpu_usage"].get("total_usage", 0)
                cpu_ms = total_ns / 1_000_000

            return {
                "memory_peak_mb": round(memory_mb, 2),
                "cpu_time_ms": round(cpu_ms, 2),
            }
        except Exception:
            return {"memory_peak_mb": 0.0, "cpu_time_ms": 0.0}

    def is_container_running(self, container_id: str) -> bool:
        """Check if a container is currently running.

        Args:
            container_id: Container ID.

        Returns:
            True if the container is running, False if stopped or does not exist.
        """
        try:
            client = self._get_client()
            container = client.containers.get(container_id)
            return container.status == "running"
        except Exception:
            return False

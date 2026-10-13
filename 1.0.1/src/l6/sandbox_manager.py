"""SandboxManager - L6 core coordination component.

Manages the full lifecycle of isolated execution environments:
create, execute, and destroy.

Directly orchestrates DockerController for container operations.
"""

import os
import shutil
import tempfile
import time
import uuid
from pathlib import Path
from typing import Dict, Optional

from src.core.models import ExecutionResult
from src.core.exceptions import SandboxCreationError
from src.l6.docker_controller import DockerController
from src.l6.config import SandboxConfig


class SandboxManager:
    """Core sandbox coordination component.

    Responsibilities:
      - Create isolated temp directories for each execution.
      - Write code to script files and run them via Docker containers.
      - Clean up temp directories and containers after execution.
      - Track environment_id -> metadata mappings.
    """

    LANGUAGE_EXTENSIONS = {
        "python": "py",
        "javascript": "js",
        "bash": "sh",
    }

    LANGUAGE_COMMANDS = {
        "python": ["python", "/sandbox/script.py"],
        "javascript": ["node", "/sandbox/script.js"],
        "bash": ["bash", "/sandbox/script.sh"],
    }

    def __init__(
        self,
        base_dir: Optional[str] = None,
        auto_cleanup: bool = True,
    ) -> None:
        self.base_dir = Path(
            base_dir or Path(tempfile.gettempdir()) / "vclaw_sandbox"
        )
        self.auto_cleanup = auto_cleanup
        self._environments: Dict[str, Dict] = {}
        self._controller = DockerController()

    def create(
        self,
        environment_id: Optional[str] = None,
        config: Optional[SandboxConfig] = None,
    ) -> str:
        """Create a new isolated environment.

        Args:
            environment_id: Optional explicit ID. If omitted, a UUID is generated.
            config: Optional sandbox configuration for this environment.

        Returns:
            The environment ID string.
        """
        if not environment_id:
            environment_id = f"env_{uuid.uuid4().hex[:8]}"

        env_path = self.base_dir / environment_id
        env_path.mkdir(parents=True, exist_ok=True)

        self._environments[environment_id] = {
            "path": str(env_path),
            "container_id": None,
            "config": config,
        }

        return environment_id

    def execute(
        self,
        environment_id: str,
        language: str,
        code: str,
        timeout: Optional[int] = 30,
    ) -> ExecutionResult:
        """Execute code inside the given environment.

        Args:
            environment_id: ID returned by create().
            language: Programming language (python, javascript, bash).
            code: Source code string.
            timeout: Execution timeout in seconds.

        Returns:
            ExecutionResult with exit_code, stdout, stderr, etc.

        Raises:
            ValueError: If environment_id does not exist.
            SandboxCreationError: If Docker container creation fails.
        """
        env_info = self._environments.get(environment_id)
        if not env_info:
            raise ValueError(f"Environment '{environment_id}' not found")

        ext = self.LANGUAGE_EXTENSIONS.get(language)
        if not ext:
            raise ValueError(f"Unsupported language: {language}")

        env_path = Path(env_info["path"])
        script_path = env_path / f"script.{ext}"
        script_path.write_text(code, encoding="utf-8")

        volumes = {
            str(env_path): {"bind": "/sandbox", "mode": "ro"}
        }

        env_config = env_info.get("config")
        mem_limit = f"{env_config.memory_limit}m" if env_config else "512m"
        cpu_quota = int(env_config.cpu_limit * 100000) if env_config else 100000
        network_mode = (
            "bridge" if (env_config and env_config.enable_network) else "none"
        )

        start_time = time.time()
        try:
            container_id = self._controller.create_container(
                language=language,
                volumes=volumes,
                mem_limit=mem_limit,
                cpu_quota=cpu_quota,
                network_mode=network_mode,
            )
        except Exception as exc:
            raise SandboxCreationError(
                f"Failed to create container: {exc}"
            ) from exc

        env_info["container_id"] = container_id

        exit_code, stdout, stderr = self._controller.exec_in_container(
            container_id,
            self.LANGUAGE_COMMANDS[language],
            timeout=timeout,
        )

        execution_time = time.time() - start_time
        resource_usage = self._controller.get_container_stats(container_id)

        return ExecutionResult(
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            execution_time=execution_time,
            resource_usage=resource_usage,
        )

    def destroy(self, environment_id: str) -> bool:
        """Destroy an environment and clean up resources.

        Args:
            environment_id: ID of the environment to destroy.

        Returns:
            True if cleanup succeeded, False if the ID did not exist
            or cleanup partially failed.
        """
        env_info = self._environments.get(environment_id)
        if not env_info:
            return False

        success = True
        container_id = env_info.get("container_id")
        if container_id:
            try:
                removed = self._controller.remove_container(container_id, force=True)
                if not removed:
                    success = False
            except Exception:
                success = False

        env_path = env_info.get("path")
        if env_path and os.path.exists(env_path):
            try:
                shutil.rmtree(env_path)
            except Exception:
                success = False

        self._environments.pop(environment_id, None)
        return success

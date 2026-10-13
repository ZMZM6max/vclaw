"""Docker sandbox for isolated code execution."""
import uuid
import time
import tempfile
import os
from pathlib import Path
from typing import Optional
from src.core.models import ExecutionResult
from src.core.exceptions import ExecutionTimeoutError
from src.l6.docker_controller import DockerController
from src.l6.config import SandboxConfig


class DockerSandbox:
    """High-level sandbox management using Docker containers.

    Manages sandbox lifecycle:
    1. Create temporary directory
    2. Create and start Docker container
    3. Write code and execute
    4. Clean up container and directory
    """

    # File extensions for each language
    EXTENSIONS = {
        "python": ".py",
        "javascript": ".js",
        "bash": ".sh"
    }

    # Command templates for each language
    COMMANDS = {
        "python": ["python", "/sandbox/script.py"],
        "javascript": ["node", "/sandbox/script.js"],
        "bash": ["bash", "/sandbox/script.sh"]
    }

    def __init__(self, config: SandboxConfig):
        """Initialize sandbox manager.

        Args:
            config: Sandbox configuration
        """
        self.config = config
        self.controller = DockerController()
        # Use cross-platform temp directory
        self.base_dir = Path(tempfile.gettempdir()) / "vclaw_sandbox"
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._environments: dict = {}

    def create(self, environment_id: Optional[str] = None) -> str:
        """Create a new sandbox environment.

        Args:
            environment_id: Optional environment ID (generated if not provided)

        Returns:
            Environment ID string
        """
        if environment_id is None:
            environment_id = f"env_{uuid.uuid4().hex[:8]}"

        # Create temporary directory
        env_path = self.base_dir / environment_id
        env_path.mkdir(parents=True, exist_ok=True)

        self._environments[environment_id] = {
            "path": env_path,
            "container_id": None
        }

        return environment_id

    def execute(
        self,
        environment_id: str,
        language: str,
        code: str,
        timeout: Optional[int] = None
    ) -> ExecutionResult:
        """Execute code in the sandbox environment.

        Args:
            environment_id: Environment ID
            language: Programming language
            code: Code to execute
            timeout: Override timeout (uses config if not provided)

        Returns:
            ExecutionResult with exit_code, stdout, stderr, execution_time

        Raises:
            ExecutionTimeoutError: If execution exceeds timeout
        """
        env_info = self._environments.get(environment_id)
        if not env_info:
            raise ValueError(f"Environment {environment_id} not found")

        env_path = env_info["path"]
        timeout = timeout or self.config.timeout

        # Write code to file
        ext = self.EXTENSIONS[language]
        script_path = env_path / f"script{ext}"
        script_path.write_text(code, encoding='utf-8')

        # Create container
        volumes = {str(env_path): {"bind": "/sandbox", "mode": "ro"}}
        mem_limit = f"{self.config.memory_limit}m"
        cpu_quota = int(self.config.cpu_limit * 100000)

        container_id = self.controller.create_container(
            language=language,
            volumes=volumes,
            mem_limit=mem_limit,
            cpu_quota=cpu_quota,
            network_mode="none" if not self.config.enable_network else "bridge"
        )

        env_info["container_id"] = container_id

        # Execute command
        command = self.COMMANDS[language]
        start_time = time.time()

        try:
            exit_code, stdout, stderr = self.controller.exec_in_container(
                container_id,
                command,
                timeout=timeout
            )
            execution_time = time.time() - start_time

            return ExecutionResult(
                exit_code=exit_code,
                stdout=stdout,
                stderr=stderr,
                execution_time=execution_time,
                resource_usage={}
            )

        except Exception as e:
            execution_time = time.time() - start_time
            return ExecutionResult(
                exit_code=1,
                stdout="",
                stderr=str(e),
                execution_time=execution_time,
                resource_usage={}
            )

    def destroy(self, environment_id: str) -> bool:
        """Destroy a sandbox environment.

        Args:
            environment_id: Environment ID to destroy

        Returns:
            True if destroyed successfully
        """
        env_info = self._environments.get(environment_id)
        if not env_info:
            return False

        # Remove container
        container_id = env_info.get("container_id")
        if container_id:
            self.controller.remove_container(container_id, force=True)

        # Remove directory
        env_path = env_info.get("path")
        if env_path and env_path.exists():
            import shutil
            try:
                shutil.rmtree(env_path)
            except Exception:
                pass

        # Remove from tracking
        del self._environments[environment_id]

        return True

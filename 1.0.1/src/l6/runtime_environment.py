"""L6 Runtime Environment.

Main class implementing RuntimeInterface. Orchestrates SecurityEnforcer,
SandboxManager, and ExecutionLogger to provide safe, isolated code execution.
"""

from typing import Optional, Dict

from src.core.interfaces import RuntimeInterface
from src.core.models import ExecutionResult
from src.core.exceptions import (
    UnsupportedLanguageError,
    SecurityViolationError,
)
from src.l6.config import SandboxConfig
from src.l6.sandbox_manager import SandboxManager
from src.l6.security_enforcer import SecurityEnforcer
from src.l6.execution_logger import ExecutionLogger


class RuntimeEnvironment(RuntimeInterface):
    """Main runtime environment implementing RuntimeInterface."""

    def __init__(self, config: Optional[SandboxConfig] = None):
        self.config = config or SandboxConfig()
        self.sandbox = SandboxManager()
        self.security_enforcer = SecurityEnforcer()
        self.execution_logger = ExecutionLogger()

    def run_code(
        self,
        language: str,
        code: str,
        timeout: int = 30,
        environment_config: Optional[Dict] = None,
    ) -> ExecutionResult:
        """Execute code in a sandboxed environment.

        Args:
            language: Programming language (python, javascript, bash).
            code: Source code string.
            timeout: Execution timeout in seconds.
            environment_config: Deprecated / unused extra config.

        Returns:
            ExecutionResult with exit_code, stdout, stderr, etc.

        Raises:
            UnsupportedLanguageError: If language is not supported.
            SecurityViolationError: If code violates security policy.
        """
        self.security_enforcer.validate_language(language)
        self.security_enforcer.check_code(code)
        self.security_enforcer.check_resource_limits(
            timeout, self.config.memory_limit, self.config.cpu_limit
        )

        environment_id = self.sandbox.create(config=self.config)
        result = None
        try:
            result = self.sandbox.execute(
                environment_id, language, code, timeout=timeout
            )
        finally:
            self.sandbox.destroy(environment_id)
            if result is not None:
                self.execution_logger.log(
                    code_hash=code[:32],
                    status="success" if result.exit_code == 0 else "error",
                    resource_usage=result.resource_usage,
                )
            else:
                self.execution_logger.log(
                    code_hash=code[:32],
                    status="error",
                    resource_usage={},
                )

        return result

    def run_command(self, command: str, timeout: int = 30) -> ExecutionResult:
        """Execute a shell command in a sandboxed environment.

        Args:
            command: Shell command string.
            timeout: Execution timeout in seconds.

        Returns:
            ExecutionResult.
        """
        return self.run_code("bash", command, timeout=timeout)

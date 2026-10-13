"""CodeExecutor - L6 language-agnostic code execution facade.

Entry point for code execution, responsible for language validation and
delegating execution to RuntimeInterface. Does not execute code directly.
"""

from typing import Optional

from src.core.interfaces import RuntimeInterface
from src.core.models import ExecutionResult
from src.core.exceptions import SandboxCreationError, UnsupportedLanguageError
from src.l6.runtime_environment import RuntimeEnvironment


class CodeExecutor:
    """Language scheduling facade for code execution.

    Responsibilities:
      - Validate requested language is in the supported list.
      - Delegate execution to RuntimeInterface.run_code().
      - Pass through ExecutionResult unchanged to the caller.
      - Support dependency injection for testability.
    """

    SUPPORTED_LANGUAGES = {"python", "javascript", "bash"}

    def __init__(self, runtime: Optional[RuntimeInterface] = None):
        """Initialize CodeExecutor with an optional runtime instance.

        Args:
            runtime: RuntimeInterface instance. If not provided, a default
                RuntimeEnvironment() is instantiated.

        Raises:
            SandboxCreationError: If RuntimeEnvironment initialization fails.
        """
        if runtime is not None:
            self.runtime = runtime
        else:
            try:
                self.runtime = RuntimeEnvironment()
            except Exception as exc:
                raise SandboxCreationError(
                    f"Failed to initialize runtime environment: {exc}"
                ) from exc

    def run(self, language: str, code: str, timeout: int = 30) -> ExecutionResult:
        """Execute code in the specified language.

        Args:
            language: Programming language. Valid values: python, javascript, bash.
            code: Source code string to execute.
            timeout: Execution timeout in seconds. Must be between 1 and 300.

        Returns:
            ExecutionResult containing exit_code, stdout, stderr, execution_time,
            and resource_usage.

        Raises:
            UnsupportedLanguageError: If the requested language is not supported.
            ValueError: If timeout is outside the allowed range (1-300).
        """
        if not (1 <= timeout <= 300):
            raise ValueError(
                f"timeout must be between 1 and 300 seconds, got {timeout}"
            )

        lang = language.lower().strip()
        if lang not in self.SUPPORTED_LANGUAGES:
            supported = ", ".join(sorted(self.SUPPORTED_LANGUAGES))
            raise UnsupportedLanguageError(
                f"Language '{language}' is not supported. "
                f"Supported languages: {supported}"
            )

        return self.runtime.run_code(lang, code, timeout=timeout)

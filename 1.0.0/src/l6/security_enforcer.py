"""Security enforcer for L6 Runtime Environment."""
import re
from typing import List, Optional
from src.core.exceptions import (
    UnsupportedLanguageError,
    SecurityViolationError
)


class SecurityEnforcer:
    """Enforces security policies for code execution."""

    # Supported programming languages
    SUPPORTED_LANGUAGES = {"python", "javascript", "bash"}

    # Forbidden patterns (security violations)
    FORBIDDEN_PATTERNS = [
        # System command execution
        r"os\.system",
        r"subprocess",
        r"os\.popen",
        # Code execution
        r"eval\s*\(",
        r"exec\s*\(",
        r"compile\s*\(",
        # Dynamic imports
        r"__import__",
        # File system operations that could be dangerous
        r"os\.unlink",
        r"os\.rmdir",
        r"shutil\.rmtree",
    ]

    # Maximum code size (100KB)
    MAX_CODE_SIZE = 100 * 1024

    def __init__(self):
        """Initialize security enforcer with compiled patterns."""
        self._compiled_patterns = [
            re.compile(pattern, re.IGNORECASE)
            for pattern in self.FORBIDDEN_PATTERNS
        ]

    def validate_language(self, language: str) -> None:
        """Validate that the language is supported.

        Args:
            language: Programming language to validate

        Raises:
            UnsupportedLanguageError: If language is not supported
        """
        language = language.lower().strip()
        if language not in self.SUPPORTED_LANGUAGES:
            raise UnsupportedLanguageError(
                f"Language '{language}' is not supported. "
                f"Supported languages: {', '.join(self.SUPPORTED_LANGUAGES)}"
            )

    def check_code(self, code: str) -> None:
        """Check code for security violations.

        Args:
            code: Code string to check

        Raises:
            SecurityViolationError: If code contains forbidden patterns
        """
        # Check code size
        if len(code) > self.MAX_CODE_SIZE:
            raise SecurityViolationError(
                f"Code size ({len(code)} bytes) exceeds maximum allowed "
                f"({self.MAX_CODE_SIZE} bytes)"
            )

        # Check for forbidden patterns
        for pattern in self._compiled_patterns:
            match = pattern.search(code)
            if match:
                raise SecurityViolationError(
                    f"Security violation: Forbidden pattern detected - '{match.group()}'"
                )

    def check_resource_limits(
        self,
        timeout: int,
        memory_limit: int,
        cpu_limit: float
    ) -> None:
        """Check if resource limits are within acceptable bounds.

        Args:
            timeout: Timeout in seconds
            memory_limit: Memory limit in MB
            cpu_limit: CPU limit in cores

        Raises:
            SecurityViolationError: If limits exceed maximum allowed
        """
        if timeout > 300:
            raise SecurityViolationError(
                f"Timeout {timeout}s exceeds maximum allowed (300s)"
            )
        if memory_limit > 4096:
            raise SecurityViolationError(
                f"Memory limit {memory_limit}MB exceeds maximum allowed (4096MB)"
            )
        if cpu_limit > 4:
            raise SecurityViolationError(
                f"CPU limit {cpu_limit} exceeds maximum allowed (4 cores)"
            )

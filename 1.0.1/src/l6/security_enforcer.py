"""Security enforcer for L6 RuntimeEnvironment.

Performs static security analysis before code execution:
- language whitelist validation
- forbidden pattern detection
- code size limits
- resource boundary checks (reads hard limits from ResourceLimiter)
"""

import re

from src.core.exceptions import UnsupportedLanguageError, SecurityViolationError
from src.l6.resource_limiter import ResourceLimiter


class SecurityEnforcer:
    """Static security analyst and resource boundary guard."""

    SUPPORTED_LANGUAGES = {"python", "javascript", "bash"}
    MAX_CODE_SIZE = 102400  # 100 * 1024 bytes

    FORBIDDEN_PATTERNS = [
        r"os\.system",
        r"os\.popen",
        r"subprocess",
        r"eval\s*\(",
        r"exec\s*\(",
        r"compile\s*\(",
        r"__import__",
        r"os\.unlink",
        r"os\.rmdir",
        r"shutil\.rmtree",
    ]

    def __init__(self):
        """Pre-compile forbidden patterns for performance."""
        self._compiled_patterns = [
            re.compile(p) for p in self.FORBIDDEN_PATTERNS
        ]

    def validate_language(self, language):
        """Validate that language is in the supported whitelist.

        Raises:
            UnsupportedLanguageError: if language is not supported.
        """
        lang = language.lower().strip()
        if lang not in self.SUPPORTED_LANGUAGES:
            supported = ", ".join(sorted(self.SUPPORTED_LANGUAGES))
            raise UnsupportedLanguageError(
                f"Language '{language}' is not supported. "
                f"Supported languages: {supported}"
            )

    def check_code(self, code):
        """Check code size and forbidden patterns.

        Raises:
            SecurityViolationError: if code is too large or contains a
            forbidden pattern.
        """
        if len(code) > self.MAX_CODE_SIZE:
            raise SecurityViolationError(
                f"Code size ({len(code)} bytes) exceeds maximum allowed "
                f"({self.MAX_CODE_SIZE} bytes)"
            )

        for pattern in self._compiled_patterns:
            match = pattern.search(code)
            if match:
                raise SecurityViolationError(
                    f"Security violation: Forbidden pattern detected - "
                    f"'{match.group()}'"
                )

    def check_resource_limits(self, timeout, memory_limit, cpu_limit):
        """Ensure requested resources do not exceed hard ceilings.

        Hard limits are read from ResourceLimiter.HARD_LIMITS so they are
        defined in a single place.

        Raises:
            SecurityViolationError: if any limit exceeds the hard ceiling.
        """
        hard = ResourceLimiter.HARD_LIMITS

        if timeout > hard["time"]:
            raise SecurityViolationError(
                f"Timeout {timeout}s exceeds maximum allowed ({hard['time']}s)"
            )

        if memory_limit > hard["memory"]:
            raise SecurityViolationError(
                f"Memory limit {memory_limit}MB exceeds maximum allowed "
                f"({hard['memory']}MB)"
            )

        if cpu_limit > hard["cpu"]:
            raise SecurityViolationError(
                f"CPU limit {cpu_limit} exceeds maximum allowed "
                f"({hard['cpu']} cores)"
            )

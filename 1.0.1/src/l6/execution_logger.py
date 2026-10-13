"""ExecutionLogger - L6 RuntimeEnvironment auxiliary component.

Records audit information for all code and command execution activities.
Used for security auditing, troubleshooting, and resource usage analysis.
"""

import time
from typing import Any


class ExecutionLogger:
    """Logger for execution activities.

    Stores logs in memory only. Not thread-safe; external locking required
    in multi-threaded environments.
    """

    def __init__(self, log_level: str = "INFO"):
        """Initialize the logger.

        Args:
            log_level: Logging level. Valid values are "INFO" and "DEBUG".
        """
        self.log_level = log_level
        self.logs: list[dict[str, Any]] = []

    def _should_log(self, status: str) -> bool:
        """Return True if the entry should be recorded at current log_level.

        Currently only INFO level is implemented; all entries are recorded.
        DEBUG level is reserved for future finer-grained filtering.
        """
        if self.log_level == "DEBUG":
            return True
        if self.log_level == "INFO":
            return True
        return False

    def log(
        self,
        code_hash: str,
        resource_usage: dict[str, Any],
        status: str,
        user_id: str = "unknown",
    ) -> None:
        """Record an execution log entry.

        Args:
            code_hash: Sanitized code identifier (truncated or hashed).
            resource_usage: Resource usage statistics dictionary.
            status: Execution result status ("success" or "error").
            user_id: User identifier. Defaults to "unknown".
        """
        if not self._should_log(status):
            return

        entry = {
            "timestamp": time.time(),
            "user_id": user_id,
            "code_hash": code_hash,
            "resource_usage": resource_usage,
            "status": status,
        }
        self.logs.append(entry)

    def get_logs(self, limit: int = 100) -> list[dict[str, Any]]:
        """Retrieve recent log entries.

        Args:
            limit: Maximum number of entries to return. Must be >= 1.

        Returns:
            The most recent *limit* log entries in reverse chronological order
            (newest first). Callers should not modify the returned dictionaries.
        """
        if limit < 1:
            raise ValueError("limit must be >= 1")
        return self.logs[-limit:][::-1]

    def clear(self) -> None:
        """Clear all in-memory logs.

        Warning:
            This operation is irreversible. Use only in testing or when
            memory is constrained.
        """
        self.logs.clear()

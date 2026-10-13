"""Resource limiter for L6 RuntimeEnvironment.

Pure dictionary operations, zero external dependencies.
Must be ready before SecurityEnforcer.
"""

from typing import Any, Dict, Optional


class ResourceLimiter:
    """Manages resource quotas for code execution.

    Provides default limits, hard ceilings, and usage checking.
    SecurityEnforcer references HARD_LIMITS during pre-flight checks.
    """

    DEFAULT_LIMITS: Dict[str, Any] = {
        "cpu": 1.0,
        "memory": 512,
        "time": 30,
        "disk": 100,
        "network": False,
    }

    HARD_LIMITS: Dict[str, Any] = {
        "cpu": 4.0,
        "memory": 4096,
        "time": 300,
        "disk": 1024,
    }

    def __init__(self, limits: Optional[Dict[str, Any]] = None) -> None:
        """Initialize with given limits or copy DEFAULT_LIMITS."""
        if limits is None:
            self.limits = self.DEFAULT_LIMITS.copy()
        else:
            self.limits = dict(limits)

    def set(self, **limits: Any) -> None:
        """Update internal limits dictionary.

        Does not validate values; validation is handled by check() and
        SecurityEnforcer.
        """
        self.limits.update(limits)

    def check(self, usage: Dict[str, Any]) -> bool:
        """Return True if all numeric usages are within limits.

        The 'network' key is skipped because it is a boolean flag.
        """
        for key, limit in self.limits.items():
            if key == "network":
                continue
            if key in usage and usage[key] > limit:
                return False
        return True

    def get_limits(self) -> Dict[str, Any]:
        """Return a shallow copy of current limits."""
        return self.limits.copy()

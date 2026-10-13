"""L6 sandbox configuration."""

from dataclasses import dataclass, field
from typing import Optional, List

from src.l6.resource_limiter import ResourceLimiter


@dataclass
class SandboxConfig:
    """Configuration for sandbox execution."""

    memory_limit: int = 512
    cpu_limit: float = 1.0
    timeout: int = 30
    enable_network: bool = False
    disk_limit: int = 100
    allowed_imports: Optional[List[str]] = None

    def __post_init__(self):
        hard = ResourceLimiter.HARD_LIMITS
        if self.memory_limit < 64 or self.memory_limit > hard["memory"]:
            raise ValueError(
                f"memory_limit must be between 64 and {hard['memory']}"
            )
        if self.cpu_limit <= 0 or self.cpu_limit > hard["cpu"]:
            raise ValueError(
                f"cpu_limit must be between 0.1 and {hard['cpu']}"
            )
        if self.timeout < 1 or self.timeout > hard["time"]:
            raise ValueError(
                f"timeout must be between 1 and {hard['time']}"
            )

"""L6 Sandbox configuration."""
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class SandboxConfig:
    """Configuration for sandbox execution environment.

    Attributes:
        memory_limit: Memory limit in MB (default: 512)
        cpu_limit: CPU limit in cores (default: 1.0)
        timeout: Execution timeout in seconds (default: 30, max: 300)
        enable_network: Whether to enable network access (default: False)
        disk_limit: Disk limit in MB (default: 100)
        allowed_imports: List of allowed Python imports (default: None = all)
    """
    memory_limit: int = 512
    cpu_limit: float = 1.0
    timeout: int = 30
    enable_network: bool = False
    disk_limit: int = 100
    allowed_imports: Optional[List[str]] = None

    def __post_init__(self):
        """Validate configuration values."""
        if self.memory_limit < 64 or self.memory_limit > 4096:
            raise ValueError("memory_limit must be between 64 and 4096 MB")
        if self.cpu_limit <= 0 or self.cpu_limit > 4:
            raise ValueError("cpu_limit must be between 0 and 4 cores")
        if self.timeout < 1 or self.timeout > 300:
            raise ValueError("timeout must be between 1 and 300 seconds")

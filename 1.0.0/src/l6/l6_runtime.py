"""L6: Runtime & Environment Layer - Docker-based sandbox code execution."""
from typing import Optional, Dict, Any
from src.core.models import ExecutionResult
from src.core.interfaces import RuntimeInterface
from src.core.exceptions import (
    UnsupportedLanguageError,
    SecurityViolationError,
    ResourceExceededError,
    ExecutionTimeoutError,
    SandboxCreationError
)
from src.l6.config import SandboxConfig
from src.l6.security_enforcer import SecurityEnforcer
from src.l6.docker_sandbox import DockerSandbox


class RuntimeEnvironment(RuntimeInterface):
    """L6 implementation - Runtime environment with Docker sandbox.

    Provides secure, isolated code execution environment with:
    - Docker container isolation
    - Resource limits (CPU, memory, time)
    - Security policy enforcement
    - Support for Python, JavaScript, and Bash

    Usage:
        runtime = RuntimeEnvironment()
        result = runtime.run_code("python", "print('Hello')", timeout=30)
        print(result.stdout)  # "Hello"
    """

    def __init__(self, config: Optional[SandboxConfig] = None):
        """Initialize runtime environment.

        Args:
            config: Sandbox configuration (uses defaults if not provided)
        """
        self.config = config or SandboxConfig()
        self.security = SecurityEnforcer()
        self.sandbox = DockerSandbox(self.config)

    def run_code(
        self,
        language: str,
        code: str,
        timeout: int = 30,
        environment_config: Optional[Dict[str, Any]] = None
    ) -> ExecutionResult:
        """Execute code in sandbox environment.

        Execution flow:
        1. Validate language support
        2. Check code security (forbidden patterns)
        3. Validate resource limits
        4. Create sandbox environment
        5. Execute code in container
        6. Clean up environment (always)
        7. Return execution result

        Args:
            language: Programming language (python, javascript, bash)
            code: Code string to execute
            timeout: Execution timeout in seconds (1-300)
            environment_config: Optional override for environment config

        Returns:
            ExecutionResult with exit_code, stdout, stderr, execution_time

        Raises:
            UnsupportedLanguageError: If language is not supported
            SecurityViolationError: If code contains forbidden patterns
            ResourceExceededError: If resource limits are exceeded
            ExecutionTimeoutError: If execution times out
            SandboxCreationError: If Docker container creation fails
        """
        # Validate language
        self.security.validate_language(language)

        # Security check
        self.security.check_code(code)

        # Check resource limits
        self.security.check_resource_limits(
            timeout=timeout,
            memory_limit=self.config.memory_limit,
            cpu_limit=self.config.cpu_limit
        )

        # Create environment
        environment_id = None
        try:
            environment_id = self.sandbox.create()

            # Execute code
            result = self.sandbox.execute(
                environment_id=environment_id,
                language=language,
                code=code,
                timeout=timeout
            )

            # Check if timeout occurred (exit code might indicate this)
            if result.exit_code == -1 or "timeout" in result.stderr.lower():
                raise ExecutionTimeoutError(
                    f"Execution timed out after {timeout} seconds"
                )

            return result

        except Exception as e:
            # Re-raise known exceptions
            if isinstance(e, (
                UnsupportedLanguageError,
                SecurityViolationError,
                ResourceExceededError,
                ExecutionTimeoutError,
                SandboxCreationError
            )):
                raise

            # Wrap unknown exceptions
            raise SandboxCreationError(f"Execution failed: {e}")

        finally:
            # Always clean up
            if environment_id:
                try:
                    self.sandbox.destroy(environment_id)
                except Exception:
                    pass  # Best effort cleanup


class SandboxManager:
    """L6 沙盒管理器

    管理隔离执行环境的创建、执行和销毁。
    """

    def __init__(self, config: SandboxConfig = None):
        self.config = config or SandboxConfig()
        self.sandbox = DockerSandbox(self.config)

    def create(self, environment_id: str, config: SandboxConfig = None) -> str:
        """创建隔离环境

        Args:
            environment_id: 环境标识
            config: 可选的沙盒配置

        Returns:
            环境ID
        """
        return self.sandbox.create(environment_id, config or self.config)

    def destroy(self, environment_id: str) -> bool:
        """销毁隔离环境

        Args:
            environment_id: 环境标识

        Returns:
            是否成功销毁
        """
        try:
            self.sandbox.destroy(environment_id)
            return True
        except Exception:
            return False

    def execute(self, environment_id: str, command: str, timeout: int = 30):
        """在沙盒内执行命令

        Args:
            environment_id: 环境标识
            command: 要执行的命令
            timeout: 超时时间（秒）

        Returns:
            执行结果
        """
        return self.sandbox.execute(environment_id, command, timeout)


class ResourceLimiter:
    """L6 资源限制器

    管理执行资源配额（CPU、内存、时间、磁盘）。
    """

    DEFAULT_LIMITS = {
        "cpu": 1.0,
        "memory": 512,
        "time": 30,
        "disk": 100,
        "network": False
    }

    def __init__(self, limits: Dict[str, Any] = None):
        self.limits = limits or self.DEFAULT_LIMITS.copy()

    def set(self, **limits) -> None:
        """设置资源限制

        Args:
            **limits: 资源限制参数
        """
        self.limits.update(limits)

    def check(self, usage: Dict[str, Any]) -> bool:
        """检查资源使用是否超限

        Args:
            usage: 当前资源使用量

        Returns:
            是否超限
        """
        for key, limit in self.limits.items():
            if key in usage and usage[key] > limit:
                return False
        return True

    def get_limits(self) -> Dict[str, Any]:
        """获取当前资源限制"""
        return self.limits.copy()


class CodeExecutor:
    """L6 代码执行器

    实际运行代码逻辑，支持Python、JavaScript、Bash。
    """

    SUPPORTED_LANGUAGES = {"python", "javascript", "bash"}

    def __init__(self, runtime: RuntimeInterface = None):
        self.runtime = runtime or RuntimeEnvironment()

    def run(self, language: str, code: str, timeout: int = 30) -> ExecutionResult:
        """运行代码

        Args:
            language: 编程语言
            code: 代码字符串
            timeout: 超时时间

        Returns:
            ExecutionResult对象
        """
        if language not in self.SUPPORTED_LANGUAGES:
            raise UnsupportedLanguageError(f"不支持的语言: {language}")
        return self.runtime.run_code(language, code, timeout=timeout)


class ExecutionLogger:
    """L6 执行日志记录器

    记录所有执行活动。
    """

    def __init__(self, log_level: str = "INFO"):
        self.log_level = log_level
        self.logs: List[Dict] = []

    def log(self, user_id: str, code_hash: str, resource_usage: Dict, status: str) -> None:
        """记录执行日志

        Args:
            user_id: 用户标识
            code_hash: 代码哈希（脱敏）
            resource_usage: 资源使用统计
            status: 执行结果状态
        """
        import time
        self.logs.append({
            "timestamp": time.time(),
            "user_id": user_id,
            "code_hash": code_hash,
            "resource_usage": resource_usage,
            "status": status
        })

    def get_logs(self, limit: int = 100) -> List[Dict]:
        """获取最近日志

        Args:
            limit: 最大返回条数

        Returns:
            日志条目列表
        """
        return self.logs[-limit:]

    def clear(self) -> None:
        """清空日志"""
        self.logs.clear()

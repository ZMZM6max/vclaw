# L6 Runtime Environment 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现基于 Docker 的安全代码执行沙盒系统，支持 Python、JavaScript、Bash 语言，包含完整的资源限制和安全策略。

**Architecture:** 采用分层组件架构：RuntimeEnvironment (门面) + DockerSandbox (沙盒管理) + DockerController (Docker API) + SecurityEnforcer (安全检查)。每个组件独立测试，通过依赖注入组合。

**Tech Stack:** Python 3.11+, Docker SDK, pytest, Pydantic (dataclass)

---

## 文件结构

```
src/l6/
├── __init__.py                 # 导出 RuntimeEnvironment
├── config.py                  # SandboxConfig 配置类
├── security_enforcer.py       # SecurityEnforcer 安全检查
├── docker_controller.py       # DockerController API 封装
├── docker_sandbox.py          # DockerSandbox 沙盒管理
├── l6_runtime.py             # RuntimeEnvironment 主类
└── tests/
    ├── __init__.py
    ├── test_security.py      # SecurityEnforcer 测试
    ├── test_docker_controller.py # DockerController 测试
    ├── test_docker_sandbox.py    # DockerSandbox 测试
    └── test_l6.py            # 集成测试
```

---

## Task 1: SandboxConfig 配置类

**Files:**
- Create: `src/l6/config.py`
- Test: `src/l6/tests/__init__.py` (ensure exists)

- [ ] **Step 1: Write SandboxConfig dataclass**

```python
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
```

- [ ] **Step 2: Create tests directory**

```bash
mkdir -p src/l6/tests
touch src/l6/tests/__init__.py
```

- [ ] **Step 3: Write test for SandboxConfig**

Create `src/l6/tests/test_config.py`:

```python
"""Tests for SandboxConfig."""
import pytest
import sys
sys.path.insert(0, 'src')

from src.l6.config import SandboxConfig


class TestSandboxConfig:
    """Tests for SandboxConfig dataclass."""
    
    def test_default_values(self):
        """Test default configuration values."""
        config = SandboxConfig()
        assert config.memory_limit == 512
        assert config.cpu_limit == 1.0
        assert config.timeout == 30
        assert config.enable_network is False
        assert config.disk_limit == 100
        assert config.allowed_imports is None
    
    def test_custom_values(self):
        """Test custom configuration values."""
        config = SandboxConfig(
            memory_limit=1024,
            cpu_limit=2.0,
            timeout=60,
            enable_network=True
        )
        assert config.memory_limit == 1024
        assert config.cpu_limit == 2.0
        assert config.timeout == 60
        assert config.enable_network is True
    
    def test_memory_limit_validation(self):
        """Test memory limit validation."""
        with pytest.raises(ValueError):
            SandboxConfig(memory_limit=32)  # Too low
        with pytest.raises(ValueError):
            SandboxConfig(memory_limit=8192)  # Too high
    
    def test_cpu_limit_validation(self):
        """Test CPU limit validation."""
        with pytest.raises(ValueError):
            SandboxConfig(cpu_limit=0)  # Too low
        with pytest.raises(ValueError):
            SandboxConfig(cpu_limit=8)  # Too high
    
    def test_timeout_validation(self):
        """Test timeout validation."""
        with pytest.raises(ValueError):
            SandboxConfig(timeout=0)  # Too low
        with pytest.raises(ValueError):
            SandboxConfig(timeout=600)  # Too high
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
python -m pytest src/l6/tests/test_config.py -v
```
Expected: All 6 tests pass

- [ ] **Step 5: Commit**

```bash
git add src/l6/config.py src/l6/tests/__init__.py src/l6/tests/test_config.py
git commit -m "feat(l6): add SandboxConfig configuration class

- Add dataclass with memory_limit, cpu_limit, timeout, enable_network, disk_limit
- Add validation in __post_init__
- Add 6 unit tests

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 2: SecurityEnforcer 安全检查

**Files:**
- Create: `src/l6/security_enforcer.py`
- Test: `src/l6/tests/test_security.py`

- [ ] **Step 1: Write SecurityEnforcer implementation**

```python
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
```

- [ ] **Step 2: Write tests for SecurityEnforcer**

Create `src/l6/tests/test_security.py`:

```python
"""Tests for SecurityEnforcer."""
import pytest
import sys
sys.path.insert(0, 'src')

from src.l6.security_enforcer import SecurityEnforcer
from src.core.exceptions import UnsupportedLanguageError, SecurityViolationError


class TestSecurityEnforcerLanguage:
    """Tests for language validation."""
    
    def test_valid_python(self):
        """Test Python is supported."""
        enforcer = SecurityEnforcer()
        enforcer.validate_language("python")  # Should not raise
    
    def test_valid_javascript(self):
        """Test JavaScript is supported."""
        enforcer = SecurityEnforcer()
        enforcer.validate_language("javascript")  # Should not raise
    
    def test_valid_bash(self):
        """Test Bash is supported."""
        enforcer = SecurityEnforcer()
        enforcer.validate_language("bash")  # Should not raise
    
    def test_invalid_language(self):
        """Test unsupported language raises error."""
        enforcer = SecurityEnforcer()
        with pytest.raises(UnsupportedLanguageError):
            enforcer.validate_language("ruby")
    
    def test_language_case_insensitive(self):
        """Test language validation is case insensitive."""
        enforcer = SecurityEnforcer()
        enforcer.validate_language("PYTHON")
        enforcer.validate_language("JavaScript")


class TestSecurityEnforcerCode:
    """Tests for code security checks."""
    
    def test_safe_code_passes(self):
        """Test safe code passes security check."""
        enforcer = SecurityEnforcer()
        safe_code = "print('Hello World')"
        enforcer.check_code(safe_code)  # Should not raise
    
    def test_os_system_blocked(self):
        """Test os.system is blocked."""
        enforcer = SecurityEnforcer()
        with pytest.raises(SecurityViolationError) as exc_info:
            enforcer.check_code("import os; os.system('rm -rf /')")
        assert "os.system" in str(exc_info.value)
    
    def test_subprocess_blocked(self):
        """Test subprocess is blocked."""
        enforcer = SecurityEnforcer()
        with pytest.raises(SecurityViolationError):
            enforcer.check_code("import subprocess; subprocess.call(['ls'])")
    
    def test_eval_blocked(self):
        """Test eval() is blocked."""
        enforcer = SecurityEnforcer()
        with pytest.raises(SecurityViolationError):
            enforcer.check_code("eval('1 + 1')")
    
    def test_exec_blocked(self):
        """Test exec() is blocked."""
        enforcer = SecurityEnforcer()
        with pytest.raises(SecurityViolationError):
            enforcer.check_code("exec('print(1)')")
    
    def test_code_size_limit(self):
        """Test code size limit is enforced."""
        enforcer = SecurityEnforcer()
        large_code = "x = 1\n" * 20000  # > 100KB
        with pytest.raises(SecurityViolationError) as exc_info:
            enforcer.check_code(large_code)
        assert "size" in str(exc_info.value).lower()


class TestSecurityEnforcerResources:
    """Tests for resource limit checks."""
    
    def test_valid_resource_limits(self):
        """Test valid resource limits pass."""
        enforcer = SecurityEnforcer()
        enforcer.check_resource_limits(timeout=30, memory_limit=512, cpu_limit=1.0)
    
    def test_timeout_too_high(self):
        """Test timeout exceeding max is blocked."""
        enforcer = SecurityEnforcer()
        with pytest.raises(SecurityViolationError):
            enforcer.check_resource_limits(timeout=600, memory_limit=512, cpu_limit=1.0)
    
    def test_memory_too_high(self):
        """Test memory exceeding max is blocked."""
        enforcer = SecurityEnforcer()
        with pytest.raises(SecurityViolationError):
            enforcer.check_resource_limits(timeout=30, memory_limit=8192, cpu_limit=1.0)
    
    def test_cpu_too_high(self):
        """Test CPU exceeding max is blocked."""
        enforcer = SecurityEnforcer()
        with pytest.raises(SecurityViolationError):
            enforcer.check_resource_limits(timeout=30, memory_limit=512, cpu_limit=8.0)
```

- [ ] **Step 3: Run tests to verify they pass**

Run:
```bash
python -m pytest src/l6/tests/test_security.py -v
```
Expected: All 15 tests pass

- [ ] **Step 4: Commit**

```bash
git add src/l6/security_enforcer.py src/l6/tests/test_security.py
git commit -m "feat(l6): implement SecurityEnforcer with code safety checks

- Add language validation (python, javascript, bash)
- Add forbidden pattern detection (os.system, subprocess, eval, exec, etc.)
- Add code size limit (100KB)
- Add resource limit validation
- Add 15 comprehensive security tests

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 3: DockerController API 封装

**Files:**
- Create: `src/l6/docker_controller.py`
- Test: `src/l6/tests/test_docker_controller.py`

- [ ] **Step 1: Write DockerController implementation**

```python
"""Docker controller for container lifecycle management."""
import time
from typing import List, Dict, Tuple, Optional
from pathlib import Path
from src.core.exceptions import SandboxCreationError


class DockerController:
    """Low-level Docker container controller.
    
    Wraps docker-py client for container creation, execution, and cleanup.
    """
    
    # Docker images for each language
    IMAGES = {
        "python": "python:3.11-alpine",
        "javascript": "node:18-alpine",
        "bash": "alpine:latest"
    }
    
    def __init__(self):
        """Initialize Docker controller."""
        self._client = None
    
    def _get_client(self):
        """Lazy initialization of Docker client."""
        if self._client is None:
            try:
                import docker
                self._client = docker.from_env()
            except ImportError:
                raise SandboxCreationError(
                    "Docker SDK not installed. Run: pip install docker"
                )
            except Exception as e:
                raise SandboxCreationError(f"Failed to connect to Docker: {e}")
        return self._client
    
    def create_container(
        self,
        language: str,
        volumes: Dict[str, Dict],
        mem_limit: str = "512m",
        cpu_quota: int = 100000,
        network_mode: str = "none"
    ) -> str:
        """Create a Docker container for code execution.
        
        Args:
            language: Programming language (determines image)
            volumes: Volume mounts {host_path: {"bind": container_path, "mode": "ro"}}
            mem_limit: Memory limit (e.g., "512m")
            cpu_quota: CPU quota in microseconds (100000 = 1 core)
            network_mode: Network mode ("none" for isolation)
            
        Returns:
            Container ID string
            
        Raises:
            SandboxCreationError: If container creation fails
        """
        client = self._get_client()
        image = self.IMAGES.get(language)
        
        if not image:
            raise SandboxCreationError(f"No Docker image for language: {language}")
        
        try:
            # Ensure image exists
            try:
                client.images.get(image)
            except:
                # Pull image if not present
                client.images.pull(image)
            
            # Create container
            container = client.containers.create(
                image=image,
                command=["sleep", "3600"],  # Keep container alive
                volumes=volumes,
                mem_limit=mem_limit,
                cpu_quota=cpu_quota,
                network_mode=network_mode,
                read_only=True,
                detach=True
            )
            
            # Start container
            container.start()
            
            return container.id
            
        except Exception as e:
            raise SandboxCreationError(f"Failed to create container: {e}")
    
    def exec_in_container(
        self,
        container_id: str,
        command: List[str],
        timeout: int = 30
    ) -> Tuple[int, str, str]:
        """Execute a command in a running container.
        
        Args:
            container_id: Docker container ID
            command: Command and arguments as list
            timeout: Timeout in seconds
            
        Returns:
            Tuple of (exit_code, stdout, stderr)
        """
        client = self._get_client()
        
        try:
            container = client.containers.get(container_id)
            
            # Execute command
            result = container.exec_run(
                cmd=command,
                stdout=True,
                stderr=True,
                stdin=False,
                tty=False
            )
            
            # Decode output
            stdout = result.output.decode('utf-8', errors='replace') if result.output else ""
            stderr = ""  # exec_run combines stdout/stderr in output
            
            # Truncate if too long
            if len(stdout) > 10000:
                stdout = stdout[:9970] + "\n[Output truncated...]"
            
            return result.exit_code, stdout, stderr
            
        except Exception as e:
            return 1, "", str(e)
    
    def remove_container(self, container_id: str, force: bool = True) -> bool:
        """Remove a Docker container.
        
        Args:
            container_id: Container ID to remove
            force: Whether to force remove running containers
            
        Returns:
            True if removed successfully, False otherwise
        """
        client = self._get_client()
        
        try:
            container = client.containers.get(container_id)
            container.remove(force=force)
            return True
        except Exception:
            return False
    
    def is_container_running(self, container_id: str) -> bool:
        """Check if a container is running.
        
        Args:
            container_id: Container ID to check
            
        Returns:
            True if running, False otherwise
        """
        client = self._get_client()
        
        try:
            container = client.containers.get(container_id)
            return container.status == "running"
        except Exception:
            return False
```

- [ ] **Step 2: Write tests for DockerController (with mocks)**

Create `src/l6/tests/test_docker_controller.py`:

```python
"""Tests for DockerController."""
import pytest
from unittest.mock import Mock, patch, MagicMock
import sys
sys.path.insert(0, 'src')

from src.l6.docker_controller import DockerController
from src.core.exceptions import SandboxCreationError


class TestDockerControllerInit:
    """Tests for DockerController initialization."""
    
    def test_lazy_client_initialization(self):
        """Test Docker client is initialized lazily."""
        controller = DockerController()
        assert controller._client is None


class TestDockerControllerCreateContainer:
    """Tests for container creation."""
    
    @patch('docker.from_env')
    def test_create_python_container(self, mock_from_env):
        """Test creating Python container."""
        # Setup mock
        mock_client = MagicMock()
        mock_container = MagicMock()
        mock_container.id = "abc123"
        mock_client.containers.create.return_value = mock_container
        mock_client.images.get.side_effect = Exception("Not found")
        mock_from_env.return_value = mock_client
        
        # Test
        controller = DockerController()
        container_id = controller.create_container(
            language="python",
            volumes={"/tmp/test": {"bind": "/sandbox", "mode": "ro"}}
        )
        
        assert container_id == "abc123"
        mock_client.containers.create.assert_called_once()
        call_kwargs = mock_client.containers.create.call_args[1]
        assert call_kwargs["image"] == "python:3.11-alpine"
        assert call_kwargs["mem_limit"] == "512m"
        assert call_kwargs["network_mode"] == "none"
    
    @patch('docker.from_env')
    def test_create_javascript_container(self, mock_from_env):
        """Test creating JavaScript container."""
        mock_client = MagicMock()
        mock_container = MagicMock()
        mock_container.id = "def456"
        mock_client.containers.create.return_value = mock_container
        mock_client.images.get.side_effect = Exception("Not found")
        mock_from_env.return_value = mock_client
        
        controller = DockerController()
        container_id = controller.create_container(
            language="javascript",
            volumes={"/tmp/test": {"bind": "/sandbox", "mode": "ro"}}
        )
        
        assert container_id == "def456"
        call_kwargs = mock_client.containers.create.call_args[1]
        assert call_kwargs["image"] == "node:18-alpine"
    
    @patch('docker.from_env')
    def test_create_container_failure(self, mock_from_env):
        """Test container creation failure."""
        mock_client = MagicMock()
        mock_client.containers.create.side_effect = Exception("Docker error")
        mock_client.images.get.side_effect = Exception("Not found")
        mock_from_env.return_value = mock_client
        
        controller = DockerController()
        with pytest.raises(SandboxCreationError):
            controller.create_container(
                language="python",
                volumes={}
            )


class TestDockerControllerExec:
    """Tests for command execution."""
    
    @patch('docker.from_env')
    def test_exec_success(self, mock_from_env):
        """Test successful command execution."""
        # Setup mock
        mock_client = MagicMock()
        mock_container = MagicMock()
        mock_result = MagicMock()
        mock_result.exit_code = 0
        mock_result.output = b"Hello World"
        mock_container.exec_run.return_value = mock_result
        mock_client.containers.get.return_value = mock_container
        mock_from_env.return_value = mock_client
        
        # Test
        controller = DockerController()
        exit_code, stdout, stderr = controller.exec_in_container(
            "abc123",
            ["python", "script.py"]
        )
        
        assert exit_code == 0
        assert stdout == "Hello World"
    
    @patch('docker.from_env')
    def test_exec_error(self, mock_from_env):
        """Test command execution with error."""
        mock_client = MagicMock()
        mock_container = MagicMock()
        mock_result = MagicMock()
        mock_result.exit_code = 1
        mock_result.output = b"Error message"
        mock_container.exec_run.return_value = mock_result
        mock_client.containers.get.return_value = mock_container
        mock_from_env.return_value = mock_client
        
        controller = DockerController()
        exit_code, stdout, stderr = controller.exec_in_container(
            "abc123",
            ["python", "script.py"]
        )
        
        assert exit_code == 1
        assert "Error" in stdout


class TestDockerControllerRemove:
    """Tests for container removal."""
    
    @patch('docker.from_env')
    def test_remove_success(self, mock_from_env):
        """Test successful container removal."""
        mock_client = MagicMock()
        mock_container = MagicMock()
        mock_client.containers.get.return_value = mock_container
        mock_from_env.return_value = mock_client
        
        controller = DockerController()
        result = controller.remove_container("abc123")
        
        assert result is True
        mock_container.remove.assert_called_once_with(force=True)
    
    @patch('docker.from_env')
    def test_remove_failure(self, mock_from_env):
        """Test container removal failure."""
        mock_client = MagicMock()
        mock_client.containers.get.side_effect = Exception("Not found")
        mock_from_env.return_value = mock_client
        
        controller = DockerController()
        result = controller.remove_container("abc123")
        
        assert result is False
```

- [ ] **Step 3: Run tests to verify they pass**

Run:
```bash
python -m pytest src/l6/tests/test_docker_controller.py -v
```
Expected: All 9 tests pass

- [ ] **Step 4: Commit**

```bash
git add src/l6/docker_controller.py src/l6/tests/test_docker_controller.py
git commit -m "feat(l6): implement DockerController for container management

- Add Docker client wrapper with lazy initialization
- Add create_container() with language-specific images
- Add exec_in_container() for command execution
- Add remove_container() for cleanup
- Add is_container_running() for status checks
- Add 9 unit tests with mocked Docker client

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 4: DockerSandbox 沙盒管理

**Files:**
- Create: `src/l6/docker_sandbox.py`
- Test: `src/l6/tests/test_docker_sandbox.py`

- [ ] **Step 1: Write DockerSandbox implementation**

```python
"""Docker sandbox for isolated code execution."""
import uuid
import time
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
        self.base_dir = Path("/tmp/sandbox")
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
        env_path.mkdir(exist_ok=True)
        
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
```

- [ ] **Step 2: Write tests for DockerSandbox**

Create `src/l6/tests/test_docker_sandbox.py`:

```python
"""Tests for DockerSandbox."""
import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import sys
sys.path.insert(0, 'src')

from src.l6.docker_sandbox import DockerSandbox
from src.l6.config import SandboxConfig
from src.core.models import ExecutionResult


class TestDockerSandboxInit:
    """Tests for DockerSandbox initialization."""
    
    def test_init_with_default_config(self):
        """Test initialization with default config."""
        config = SandboxConfig()
        sandbox = DockerSandbox(config)
        
        assert sandbox.config == config
        assert sandbox.base_dir == Path("/tmp/sandbox")
        assert sandbox._environments == {}
    
    def test_init_creates_base_dir(self, tmp_path):
        """Test initialization creates base directory."""
        config = SandboxConfig()
        sandbox = DockerSandbox(config)
        assert sandbox.base_dir.exists()


class TestDockerSandboxCreate:
    """Tests for sandbox creation."""
    
    def test_create_generates_id(self):
        """Test create generates environment ID."""
        config = SandboxConfig()
        sandbox = DockerSandbox(config)
        
        env_id = sandbox.create()
        
        assert env_id.startswith("env_")
        assert len(env_id) == 12  # env_ + 8 chars
        assert env_id in sandbox._environments
    
    def test_create_with_custom_id(self):
        """Test create with custom environment ID."""
        config = SandboxConfig()
        sandbox = DockerSandbox(config)
        
        env_id = sandbox.create("my_custom_id")
        
        assert env_id == "my_custom_id"
        assert env_id in sandbox._environments
    
    def test_create_creates_directory(self, tmp_path):
        """Test create creates environment directory."""
        config = SandboxConfig()
        sandbox = DockerSandbox(config)
        sandbox.base_dir = tmp_path / "sandbox"
        
        env_id = sandbox.create("test_env")
        
        assert (sandbox.base_dir / "test_env").exists()


class TestDockerSandboxExecute:
    """Tests for code execution."""
    
    @patch('src.l6.docker_sandbox.DockerController')
    def test_execute_python(self, mock_controller_class):
        """Test executing Python code."""
        # Setup mocks
        mock_controller = MagicMock()
        mock_controller.create_container.return_value = "container123"
        mock_controller.exec_in_container.return_value = (0, "Hello", "")
        mock_controller_class.return_value = mock_controller
        
        # Create sandbox
        config = SandboxConfig()
        sandbox = DockerSandbox(config)
        sandbox.base_dir = Path("/tmp")
        
        # Create environment and write code
        env_id = sandbox.create("test_env")
        
        # Execute
        result = sandbox.execute(env_id, "python", "print('Hello')")
        
        # Verify
        assert isinstance(result, ExecutionResult)
        assert result.exit_code == 0
        assert result.stdout == "Hello"
        mock_controller.create_container.assert_called_once()
        mock_controller.exec_in_container.assert_called_once_with(
            "container123",
            ["python", "/sandbox/script.py"],
            timeout=30
        )
    
    @patch('src.l6.docker_sandbox.DockerController')
    def test_execute_javascript(self, mock_controller_class):
        """Test executing JavaScript code."""
        mock_controller = MagicMock()
        mock_controller.create_container.return_value = "container456"
        mock_controller.exec_in_container.return_value = (0, "Hello JS", "")
        mock_controller_class.return_value = mock_controller
        
        config = SandboxConfig()
        sandbox = DockerSandbox(config)
        sandbox.base_dir = Path("/tmp")
        
        env_id = sandbox.create("test_env")
        result = sandbox.execute(env_id, "javascript", "console.log('Hello')")
        
        assert result.exit_code == 0
        mock_controller.exec_in_container.assert_called_once_with(
            "container456",
            ["node", "/sandbox/script.js"],
            timeout=30
        )
    
    @patch('src.l6.docker_sandbox.DockerController')
    def test_execute_error(self, mock_controller_class):
        """Test execution with error."""
        mock_controller = MagicMock()
        mock_controller.create_container.return_value = "container789"
        mock_controller.exec_in_container.return_value = (1, "", "Error")
        mock_controller_class.return_value = mock_controller
        
        config = SandboxConfig()
        sandbox = DockerSandbox(config)
        sandbox.base_dir = Path("/tmp")
        
        env_id = sandbox.create("test_env")
        result = sandbox.execute(env_id, "python", "invalid syntax")
        
        assert result.exit_code == 1
        assert "Error" in result.stderr


class TestDockerSandboxDestroy:
    """Tests for sandbox destruction."""
    
    def test_destroy_removes_environment(self):
        """Test destroy removes environment."""
        config = SandboxConfig()
        sandbox = DockerSandbox(config)
        sandbox.base_dir = Path("/tmp")
        
        env_id = sandbox.create("test_env")
        result = sandbox.destroy(env_id)
        
        assert result is True
        assert env_id not in sandbox._environments
    
    def test_destroy_nonexistent_returns_false(self):
        """Test destroy non-existent environment returns False."""
        config = SandboxConfig()
        sandbox = DockerSandbox(config)
        
        result = sandbox.destroy("nonexistent")
        
        assert result is False
    
    @patch('src.l6.docker_sandbox.DockerController')
    def test_destroy_removes_container(self, mock_controller_class):
        """Test destroy removes Docker container."""
        mock_controller = MagicMock()
        mock_controller_class.return_value = mock_controller
        
        config = SandboxConfig()
        sandbox = DockerSandbox(config)
        sandbox.base_dir = Path("/tmp")
        
        env_id = sandbox.create("test_env")
        sandbox._environments[env_id]["container_id"] = "container123"
        
        sandbox.destroy(env_id)
        
        mock_controller.remove_container.assert_called_once_with(
            "container123", force=True
        )
```

- [ ] **Step 3: Run tests to verify they pass**

Run:
```bash
python -m pytest src/l6/tests/test_docker_sandbox.py -v
```
Expected: All 10 tests pass

- [ ] **Step 4: Commit**

```bash
git add src/l6/docker_sandbox.py src/l6/tests/test_docker_sandbox.py
git commit -m "feat(l6): implement DockerSandbox for high-level sandbox management

- Add sandbox lifecycle management (create/execute/destroy)
- Add language-specific command generation (python/js/bash)
- Add temporary directory management
- Add container cleanup on destroy
- Add 10 unit tests with mocked dependencies

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 5: RuntimeEnvironment 主类

**Files:**
- Modify: `src/l6/l6_runtime.py` (complete rewrite)
- Test: `src/l6/tests/test_l6.py` (update existing tests)

- [ ] **Step 1: Rewrite l6_runtime.py with full implementation**

```python
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
```

- [ ] **Step 2: Update existing tests**

Update `src/l6/tests/test_l6.py`:

```python
"""Tests for L6 Runtime Environment."""
import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import sys
sys.path.insert(0, 'src')

from src.l6.l6_runtime import RuntimeEnvironment
from src.l6.config import SandboxConfig
from src.core.models import ExecutionResult
from src.core.exceptions import (
    UnsupportedLanguageError,
    SecurityViolationError,
    ExecutionTimeoutError
)


class TestRuntimeEnvironmentInit:
    """Tests for RuntimeEnvironment initialization."""
    
    def test_init_with_default_config(self):
        """Test initialization with default config."""
        runtime = RuntimeEnvironment()
        assert runtime.config is not None
        assert isinstance(runtime.config, SandboxConfig)
    
    def test_init_with_custom_config(self):
        """Test initialization with custom config."""
        config = SandboxConfig(memory_limit=1024, timeout=60)
        runtime = RuntimeEnvironment(config)
        assert runtime.config.memory_limit == 1024
        assert runtime.config.timeout == 60


class TestRuntimeEnvironmentRunCode:
    """Tests for run_code method."""
    
    @patch('src.l6.l6_runtime.DockerSandbox')
    def test_run_python_success(self, mock_sandbox_class):
        """Test successful Python execution."""
        # Setup mocks
        mock_sandbox = MagicMock()
        mock_sandbox.create.return_value = "env123"
        mock_sandbox.execute.return_value = ExecutionResult(
            exit_code=0,
            stdout="Hello World",
            stderr="",
            execution_time=0.5
        )
        mock_sandbox_class.return_value = mock_sandbox
        
        # Test
        runtime = RuntimeEnvironment()
        result = runtime.run_code("python", "print('Hello World')")
        
        # Verify
        assert isinstance(result, ExecutionResult)
        assert result.exit_code == 0
        assert result.stdout == "Hello World"
        mock_sandbox.create.assert_called_once()
        mock_sandbox.execute.assert_called_once()
        mock_sandbox.destroy.assert_called_once_with("env123")
    
    def test_run_unsupported_language(self):
        """Test unsupported language raises error."""
        runtime = RuntimeEnvironment()
        
        with pytest.raises(UnsupportedLanguageError):
            runtime.run_code("ruby", "puts 'Hello'")
    
    def test_run_forbidden_code(self):
        """Test forbidden code raises security error."""
        runtime = RuntimeEnvironment()
        
        with pytest.raises(SecurityViolationError):
            runtime.run_code("python", "import os; os.system('ls')")
    
    @patch('src.l6.l6_runtime.DockerSandbox')
    def test_cleanup_on_error(self, mock_sandbox_class):
        """Test cleanup happens even on error."""
        mock_sandbox = MagicMock()
        mock_sandbox.create.return_value = "env456"
        mock_sandbox.execute.side_effect = Exception("Execution failed")
        mock_sandbox_class.return_value = mock_sandbox
        
        runtime = RuntimeEnvironment()
        
        with pytest.raises(Exception):
            runtime.run_code("python", "print('test')")
        
        # Cleanup should still be called
        mock_sandbox.destroy.assert_called_once_with("env456")


class TestRuntimeEnvironmentLanguages:
    """Tests for different language support."""
    
    @patch('src.l6.l6_runtime.DockerSandbox')
    def test_run_javascript(self, mock_sandbox_class):
        """Test JavaScript execution."""
        mock_sandbox = MagicMock()
        mock_sandbox.create.return_value = "env_js"
        mock_sandbox.execute.return_value = ExecutionResult(
            exit_code=0,
            stdout="JS output",
            stderr="",
            execution_time=0.3
        )
        mock_sandbox_class.return_value = mock_sandbox
        
        runtime = RuntimeEnvironment()
        result = runtime.run_code("javascript", "console.log('test')")
        
        assert result.exit_code == 0
        assert result.stdout == "JS output"
    
    @patch('src.l6.l6_runtime.DockerSandbox')
    def test_run_bash(self, mock_sandbox_class):
        """Test Bash execution."""
        mock_sandbox = MagicMock()
        mock_sandbox.create.return_value = "env_bash"
        mock_sandbox.execute.return_value = ExecutionResult(
            exit_code=0,
            stdout="Bash output",
            stderr="",
            execution_time=0.1
        )
        mock_sandbox_class.return_value = mock_sandbox
        
        runtime = RuntimeEnvironment()
        result = runtime.run_code("bash", "echo 'test'")
        
        assert result.exit_code == 0
        assert result.stdout == "Bash output"


class TestRuntimeEnvironmentSecurity:
    """Tests for security features."""
    
    def test_code_size_limit(self):
        """Test code size limit is enforced."""
        runtime = RuntimeEnvironment()
        large_code = "x = 1\n" * 20000  # > 100KB
        
        with pytest.raises(SecurityViolationError) as exc_info:
            runtime.run_code("python", large_code)
        
        assert "size" in str(exc_info.value).lower()
    
    def test_eval_blocked(self):
        """Test eval() is blocked."""
        runtime = RuntimeEnvironment()
        
        with pytest.raises(SecurityViolationError):
            runtime.run_code("python", "eval('1 + 1')")
    
    def test_exec_blocked(self):
        """Test exec() is blocked."""
        runtime = RuntimeEnvironment()
        
        with pytest.raises(SecurityViolationError):
            runtime.run_code("python", "exec('print(1)')")
```

- [ ] **Step 3: Run all L6 tests to verify**

Run:
```bash
python -m pytest src/l6/tests/ -v
```
Expected: All 40+ tests pass

- [ ] **Step 4: Commit**

```bash
git add src/l6/l6_runtime.py src/l6/tests/test_l6.py
git commit -m "feat(l6): complete RuntimeEnvironment implementation

- Rewrite RuntimeEnvironment with full Docker sandbox integration
- Add complete security pipeline (language, code, resource checks)
- Add automatic cleanup in finally block
- Add comprehensive integration tests (13 tests)
- Support Python, JavaScript, and Bash execution

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 6: Package Integration

**Files:**
- Modify: `src/l6/__init__.py`
- Modify: `requirements.txt` (add docker dependency)

- [ ] **Step 1: Update __init__.py**

```python
"""L6: Runtime & Environment Layer"""
from src.l6.l6_runtime import RuntimeEnvironment
from src.l6.config import SandboxConfig

__all__ = ['RuntimeEnvironment', 'SandboxConfig']
```

- [ ] **Step 2: Add docker to requirements.txt**

Add to `requirements.txt`:
```
# L6 Runtime Environment
docker>=6.0.0
```

- [ ] **Step 3: Run final test suite**

Run:
```bash
python -m pytest src/l6/tests/ -v --tb=short
```
Expected: All tests pass

- [ ] **Step 4: Commit**

```bash
git add src/l6/__init__.py requirements.txt
git commit -m "chore(l6): add package exports and dependencies

- Export RuntimeEnvironment and SandboxConfig from l6 package
- Add docker>=6.0.0 to requirements.txt

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## 验证清单

实施完成后，确认以下功能正常工作：

- [ ] `SandboxConfig` 配置验证
- [ ] `SecurityEnforcer` 安全检查和禁止模式检测
- [ ] `DockerController` 容器生命周期管理
- [ ] `DockerSandbox` 沙盒创建/执行/销毁
- [ ] `RuntimeEnvironment` 完整执行流程
- [ ] 所有 40+ 测试通过
- [ ] 支持 Python、JavaScript、Bash 三种语言
- [ ] 资源限制（CPU、内存、时间）有效
- [ ] 异常处理正确（超时、安全违规、不支持的语言）

---

**计划完成！** 执行选项：

1. **Subagent-Driven (推荐)** - 每个任务分配独立子代理，任务间审查
2. **Inline Execution** - 当前会话使用 executing-plans 顺序执行

**计划文件保存至**: `docs/superpowers/plans/2026-04-13-l6-runtime-environment-plan.md`

你想使用哪种方式执行？

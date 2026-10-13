# L5 file_delete 高危操作工具实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 完整实现 L5 层的 file_delete 工具，包含二次确认机制、沙盒路径验证，并确保 100% 测试覆盖。

**Architecture:** 在现有 L5 架构基础上新增 `ConfirmationManager` 组件管理待确认操作状态，增强 `ParameterValidator` 的沙盒路径验证，通过 TDD 模式逐步构建。

**Tech Stack:** Python 3.11+, pytest, Pydantic, 现有 VClaw 六层架构

---

## 文件结构

```
src/
├── core/
│   └── exceptions.py              # 新增 ConfirmationRequiredError 等
├── l5/
│   ├── __init__.py                # 导出 ConfirmationManager
│   ├── confirmation_manager.py    # 新增：待确认操作管理
│   ├── l5_tools.py                # 修改：添加 file_delete 支持
│   └── tests/
│       ├── test_confirmation.py   # 新增：二次确认测试
│       ├── test_path_validation.py# 新增：路径验证测试
│       └── README.md              # 修改：更新测试文档
```

---

## Task 1: 新增异常类型

**Files:**
- Modify: `src/core/exceptions.py`
- Test: `src/l5/tests/test_confirmation.py` (部分)

**Context:** 需要定义 file_delete 二次确认相关的异常类型。

- [ ] **Step 1: 在 exceptions.py 添加 ConfirmationRequiredError**

```python
# src/core/exceptions.py - 在文件末尾添加


# ==================== L5: Tools & Capabilities Exceptions (Additional) ====================

class ConfirmationRequiredError(VClawException):
    """Raised when user confirmation is required for high-risk operations.
    
    This is not a true error but a state indicator that requires user interaction.
    """
    def __init__(self, message: str, confirmation_id: str, affected_count: int = 1):
        super().__init__(message)
        self.confirmation_id = confirmation_id
        self.affected_count = affected_count


class ConfirmationExpiredError(VClawException):
    """Raised when confirmation has expired."""
    pass


class InvalidConfirmationError(VClawException):
    """Raised when confirmation_id is invalid or has been consumed."""
    pass
```

- [ ] **Step 2: 验证异常导入正常**

Run:
```bash
python -c "from src.core.exceptions import ConfirmationRequiredError, ConfirmationExpiredError, InvalidConfirmationError; print('Import OK')"
```

Expected: `Import OK`

- [ ] **Step 3: Commit**

```bash
git add src/core/exceptions.py
git commit -m "feat(l5): add confirmation-related exceptions for file_delete"
```

---

## Task 2: 实现 ConfirmationManager

**Files:**
- Create: `src/l5/confirmation_manager.py`
- Test: `src/l5/tests/test_confirmation.py` (部分)

**Context:** 管理需要二次确认的高危操作，内存存储，300秒TTL。

- [ ] **Step 1: 编写 ConfirmationManager 的测试**

```python
# src/l5/tests/test_confirmation.py - 创建文件
"""Tests for ConfirmationManager."""
import pytest
import time
from unittest.mock import patch
import sys
sys.path.insert(0, 'src')

from src.l5.confirmation_manager import ConfirmationManager, PendingOperation
from src.core.exceptions import ConfirmationExpiredError, InvalidConfirmationError


class TestConfirmationManager:
    """Tests for confirmation management."""

    def test_create_pending_returns_confirmation_id(self):
        """TC-L5-CONFIRM-001: 创建待确认记录返回 confirmation_id"""
        # Arrange
        manager = ConfirmationManager()
        params = {"path": "documents/test.txt", "confirmed": False}

        # Act
        confirmation_id = manager.create_pending("file_delete", params)

        # Assert
        assert isinstance(confirmation_id, str)
        assert len(confirmation_id) > 0

    def test_get_pending_returns_operation(self):
        """获取有效的待确认操作"""
        # Arrange
        manager = ConfirmationManager()
        params = {"path": "documents/test.txt"}
        confirmation_id = manager.create_pending("file_delete", params)

        # Act
        pending = manager.get_pending(confirmation_id)

        # Assert
        assert pending is not None
        assert pending.tool_name == "file_delete"
        assert pending.params["path"] == "documents/test.txt"
        assert pending.confirmation_id == confirmation_id

    def test_confirm_and_execute_consumes_record(self):
        """TC-L5-CONFIRM-002: 确认后消费记录"""
        # Arrange
        manager = ConfirmationManager()
        params = {"path": "documents/test.txt"}
        confirmation_id = manager.create_pending("file_delete", params)

        # Act
        pending = manager.confirm_and_consume(confirmation_id)

        # Assert
        assert pending.tool_name == "file_delete"
        assert pending.params["path"] == "documents/test.txt"
        # Record should be removed
        assert manager.get_pending(confirmation_id) is None

    def test_invalid_confirmation_id_raises_error(self):
        """TC-L5-CONFIRM-003: 无效 confirmation_id 抛出异常"""
        # Arrange
        manager = ConfirmationManager()

        # Act & Assert
        with pytest.raises(InvalidConfirmationError):
            manager.confirm_and_consume("invalid-id-12345")

    def test_expired_confirmation_returns_none(self):
        """TC-L5-CONFIRM-004: 过期确认返回 None"""
        # Arrange
        manager = ConfirmationManager(ttl_seconds=0)  # 0 second TTL
        params = {"path": "documents/test.txt"}
        confirmation_id = manager.create_pending("file_delete", params)
        time.sleep(0.1)  # Wait for expiration

        # Act
        pending = manager.get_pending(confirmation_id)

        # Assert
        assert pending is None

    def test_cleanup_expired_removes_old_records(self):
        """过期记录清理"""
        # Arrange
        manager = ConfirmationManager(ttl_seconds=0)
        confirmation_id = manager.create_pending("file_delete", {"path": "test.txt"})
        time.sleep(0.1)

        # Act - calling get_pending triggers cleanup
        manager.get_pending(confirmation_id)

        # Assert - internal _pending dict should be empty
        assert len(manager._pending) == 0
```

- [ ] **Step 2: 运行测试确保失败（TDD Red）**

Run:
```bash
pytest src/l5/tests/test_confirmation.py -v
```

Expected: 6 个测试全部 FAIL（ModuleNotFoundError）

- [ ] **Step 3: 实现 ConfirmationManager**

```python
# src/l5/confirmation_manager.py - 创建文件
"""Confirmation manager for high-risk operations requiring user confirmation."""
import uuid
import time
from dataclasses import dataclass
from typing import Dict, Any, Optional
from src.core.exceptions import ConfirmationExpiredError, InvalidConfirmationError


@dataclass
class PendingOperation:
    """Represents a pending operation awaiting user confirmation."""
    confirmation_id: str
    tool_name: str
    params: Dict[str, Any]
    created_at: float
    expires_at: float


class ConfirmationManager:
    """Manages pending operations that require user confirmation.
    
    Features:
    - In-memory storage of pending operations
    - TTL-based automatic expiration (default: 300 seconds)
    - Automatic cleanup of expired records
    - UUID-based confirmation IDs for security
    """
    
    DEFAULT_TTL = 300  # 5 minutes
    
    def __init__(self, ttl_seconds: int = DEFAULT_TTL):
        """Initialize the confirmation manager.
        
        Args:
            ttl_seconds: Time-to-live for pending operations in seconds
        """
        self._ttl = ttl_seconds
        self._pending: Dict[str, PendingOperation] = {}
    
    def create_pending(self, tool_name: str, params: Dict[str, Any]) -> str:
        """Create a new pending operation.
        
        Args:
            tool_name: Name of the tool to be executed
            params: Parameters for the tool execution
            
        Returns:
            Confirmation ID (UUID) for retrieving/consuming the operation
        """
        confirmation_id = str(uuid.uuid4())
        now = time.time()
        
        operation = PendingOperation(
            confirmation_id=confirmation_id,
            tool_name=tool_name,
            params=params.copy(),
            created_at=now,
            expires_at=now + self._ttl
        )
        
        self._pending[confirmation_id] = operation
        return confirmation_id
    
    def get_pending(self, confirmation_id: str) -> Optional[PendingOperation]:
        """Get a pending operation if it exists and is not expired.
        
        Args:
            confirmation_id: The confirmation ID to look up
            
        Returns:
            PendingOperation if found and not expired, None otherwise
        """
        self._cleanup_expired()
        
        operation = self._pending.get(confirmation_id)
        if operation is None:
            return None
            
        if time.time() > operation.expires_at:
            # Expired - remove it
            del self._pending[confirmation_id]
            return None
            
        return operation
    
    def confirm_and_consume(self, confirmation_id: str) -> PendingOperation:
        """Confirm and consume a pending operation.
        
        Args:
            confirmation_id: The confirmation ID to confirm
            
        Returns:
            The PendingOperation that was confirmed
            
        Raises:
            InvalidConfirmationError: If confirmation_id is invalid or expired
        """
        self._cleanup_expired()
        
        operation = self._pending.get(confirmation_id)
        if operation is None:
            raise InvalidConfirmationError(
                f"Confirmation ID '{confirmation_id}' is invalid or has expired"
            )
        
        # Consume the operation
        del self._pending[confirmation_id]
        return operation
    
    def _cleanup_expired(self):
        """Remove all expired pending operations."""
        now = time.time()
        expired_ids = [
            cid for cid, op in self._pending.items()
            if now > op.expires_at
        ]
        for cid in expired_ids:
            del self._pending[cid]
```

- [ ] **Step 4: 运行测试确保通过（TDD Green）**

Run:
```bash
pytest src/l5/tests/test_confirmation.py -v
```

Expected: 6 个测试全部 PASS

- [ ] **Step 5: Commit**

```bash
git add src/l5/confirmation_manager.py src/l5/tests/test_confirmation.py
git commit -m "feat(l5): implement ConfirmationManager with TTL and cleanup"
```

---

## Task 3: 增强 ParameterValidator 沙盒路径验证

**Files:**
- Modify: `src/l5/l5_tools.py` (ParameterValidator 类)
- Test: `src/l5/tests/test_path_validation.py` (新建)

**Context:** 根据 XML 规范，文件操作工具需要强制 `documents/` 前缀。

- [ ] **Step 1: 编写沙盒路径验证测试**

```python
# src/l5/tests/test_path_validation.py - 创建文件
"""Tests for enhanced path validation."""
import pytest
import sys
sys.path.insert(0, 'src')

from src.l5.l5_tools import ParameterValidator, ValidationResult


class TestSandboxPathValidation:
    """Tests for sandbox path validation (TC-L5-PATH-002, TC-L5-PATH-003)."""

    def test_valid_documents_path_passes(self):
        """有效的 documents/ 路径通过验证"""
        # Arrange
        validator = ParameterValidator()
        
        # Act & Assert
        valid_paths = [
            "documents/file.txt",
            "documents/desktop/report.pdf",
            "documents/downloads/data.csv",
            "documents/subdir/nested/file.py"
        ]
        
        for path in valid_paths:
            result = validator.validate_sandbox_path(path)
            assert result.valid, f"Path '{path}' should be valid but got: {result.errors}"

    def test_missing_documents_prefix_fails(self):
        """TC-L5-PATH-002: 缺少 documents/ 前缀被拒绝"""
        # Arrange
        validator = ParameterValidator()
        
        # Act
        result = validator.validate_sandbox_path("file.txt")
        
        # Assert
        assert not result.valid
        assert "documents/" in result.errors[0].lower()

    def test_directory_traversal_fails(self):
        """TC-L5-PATH-003: 目录遍历攻击被拒绝"""
        # Arrange
        validator = ParameterValidator()
        
        # Act & Assert
        dangerous_paths = [
            "documents/../etc/passwd",
            "documents/subdir/../../../etc/shadow",
            "../windows/system32",
            "documents/..\\windows\\system32"
        ]
        
        for path in dangerous_paths:
            result = validator.validate_sandbox_path(path)
            assert not result.valid, f"Path '{path}' should be rejected"
            assert ".." in result.errors[0] or "traversal" in result.errors[0].lower()

    def test_absolute_path_fails(self):
        """绝对路径被拒绝"""
        # Arrange
        validator = ParameterValidator()
        
        # Act & Assert
        absolute_paths = [
            "/etc/passwd",
            "/usr/bin/python",
            "C:\\Windows\\system32",
            "D:\\data\\file.txt"
        ]
        
        for path in absolute_paths:
            result = validator.validate_sandbox_path(path)
            assert not result.valid, f"Absolute path '{path}' should be rejected"

    def test_path_safety_backward_compatible(self):
        """现有 is_path_safe() 方法保持向后兼容"""
        # Arrange
        validator = ParameterValidator()
        
        # Act & Assert - existing dangerous patterns
        dangerous = ["../../../etc/passwd", "..\\windows\\system32"]
        for path in dangerous:
            assert not validator.is_path_safe(path)
        
        safe = ["data/file.txt", "script.py"]
        for path in safe:
            assert validator.is_path_safe(path)
```

- [ ] **Step 2: 运行测试确保失败（TDD Red）**

Run:
```bash
pytest src/l5/tests/test_path_validation.py -v
```

Expected: 5 个测试全部 FAIL（AttributeError: validate_sandbox_path）

- [ ] **Step 3: 在 ParameterValidator 中添加 validate_sandbox_path 方法**

```python
# src/l5/l5_tools.py - 在 ParameterValidator 类中添加新方法

class ParameterValidator:
    """Parameter validator with security checks."""

    # 现有代码保持不变...
    DANGEROUS_PATH_PATTERNS = [...]
    SAFE_TERMINAL_COMMANDS = [...]
    DANGEROUS_COMMANDS = [...]
    
    # 新增：沙盒根目录
    SANDBOX_ROOT = "documents/"

    @staticmethod
    def validate(params: Dict, schema: Dict) -> "ValidationResult":
        """现有 validate 方法保持不变"""
        # ... 现有代码 ...

    @staticmethod
    def is_path_safe(path: str) -> bool:
        """现有 is_path_safe 方法保持不变（向后兼容）"""
        # ... 现有代码 ...

    @staticmethod
    def sanitize_path(path: str, base_dir: str = ".") -> str:
        """现有 sanitize_path 方法保持不变"""
        # ... 现有代码 ...

    # ===== 新增方法 =====
    
    @staticmethod
    def validate_sandbox_path(path: str) -> "ValidationResult":
        """Validate that a path is within the sandbox (documents/ prefix required).
        
        According to XML spec, file operations must use paths starting with 'documents/'.
        
        Args:
            path: The path to validate
            
        Returns:
            ValidationResult with valid flag and error messages
        """
        errors = []
        
        # Rule 1: Must start with documents/
        if not path.startswith("documents/"):
            errors.append("路径必须在沙盒范围内，必须以 'documents/' 开头")
        
        # Rule 2: No directory traversal
        if ".." in path:
            errors.append("检测到目录遍历攻击，路径包含非法字符 '..'")
        
        # Rule 3: No absolute paths
        if path.startswith("/") or re.match(r'^[A-Za-z]:\\', path):
            errors.append("禁止使用绝对路径")
        
        # Rule 4: Check against existing dangerous patterns
        for pattern in ParameterValidator.DANGEROUS_PATH_PATTERNS:
            if re.search(pattern, path, re.IGNORECASE):
                errors.append(f"路径包含非法模式")
                break
        
        return ValidationResult(valid=len(errors) == 0, errors=errors)

    # 现有 validate_terminal_command 保持不变
```

- [ ] **Step 4: 运行测试确保通过（TDD Green）**

Run:
```bash
pytest src/l5/tests/test_path_validation.py -v
```

Expected: 5 个测试全部 PASS

- [ ] **Step 5: Commit**

```bash
git add src/l5/l5_tools.py src/l5/tests/test_path_validation.py
git commit -m "feat(l5): add sandbox path validation (documents/ prefix required)"
```

---

## Task 4: 实现 file_delete 工具

**Files:**
- Modify: `src/l5/l5_tools.py` (ToolsCapabilities 类)
- Test: `src/l5/tests/test_confirmation.py` (添加测试)

**Context:** 实现 file_delete 工具，包含二次确认机制。

- [ ] **Step 1: 编写 file_delete 工具测试**

```python
# src/l5/tests/test_confirmation.py - 在文件末尾追加


class TestFileDeleteTool:
    """Tests for file_delete tool with confirmation flow."""

    def test_file_delete_first_request_returns_confirmation_required(self, tmp_path):
        """TC-L5-CONFIRM-001: 首次删除请求返回 confirmation_required"""
        # Arrange
        from src.l5.l5_tools import ToolsCapabilities
        tools = ToolsCapabilities()
        
        # Create test file
        test_file = tmp_path / "documents" / "test.txt"
        test_file.parent.mkdir(parents=True)
        test_file.write_text("test content")
        
        # Act
        result = tools.execute(
            "file_delete",
            {"path": str(test_file.relative_to(tmp_path)), "confirmed": False}
        )
        
        # Assert
        assert result.status == "confirmation_required"
        assert "confirmation_id" in result.metadata
        assert result.metadata["affected_count"] == 1
        assert "确定要删除" in result.result

    def test_file_delete_confirm_and_execute(self, tmp_path):
        """TC-L5-CONFIRM-002: 确认后执行删除"""
        # Arrange
        from src.l5.l5_tools import ToolsCapabilities
        tools = ToolsCapabilities()
        
        test_file = tmp_path / "documents" / "test.txt"
        test_file.parent.mkdir(parents=True)
        test_file.write_text("test content")
        
        # Step 1: Request confirmation
        result1 = tools.execute(
            "file_delete",
            {"path": str(test_file.relative_to(tmp_path)), "confirmed": False}
        )
        confirmation_id = result1.metadata["confirmation_id"]
        
        # Step 2: Confirm and execute
        result2 = tools.execute(
            "file_delete",
            {
                "path": str(test_file.relative_to(tmp_path)),
                "confirmed": True,
                "confirmation_id": confirmation_id
            }
        )
        
        # Assert
        assert result2.status == "success"
        assert not test_file.exists()
        assert "已成功删除" in result2.result

    def test_file_delete_invalid_confirmation_id_fails(self, tmp_path):
        """TC-L5-CONFIRM-003: 无效 confirmation_id 返回错误"""
        # Arrange
        from src.l5.l5_tools import ToolsCapabilities
        tools = ToolsCapabilities()
        
        test_file = tmp_path / "documents" / "test.txt"
        test_file.parent.mkdir(parents=True)
        test_file.write_text("test")
        
        # Act
        result = tools.execute(
            "file_delete",
            {
                "path": str(test_file.relative_to(tmp_path)),
                "confirmed": True,
                "confirmation_id": "invalid-id-12345"
            }
        )
        
        # Assert
        assert result.status == "error"
        assert "invalid" in result.result.lower() or "过期" in result.result

    def test_file_delete_expired_confirmation_fails(self, tmp_path):
        """TC-L5-CONFIRM-004: 过期确认返回错误"""
        # Arrange
        from src.l5.l5_tools import ToolsCapabilities
        from src.l5.confirmation_manager import ConfirmationManager
        
        # Create tools with 0-second TTL confirmation manager
        tools = ToolsCapabilities()
        tools.confirmation_manager = ConfirmationManager(ttl_seconds=0)
        
        test_file = tmp_path / "documents" / "test.txt"
        test_file.parent.mkdir(parents=True)
        test_file.write_text("test")
        
        # Step 1: Request confirmation (will expire immediately)
        result1 = tools.execute(
            "file_delete",
            {"path": str(test_file.relative_to(tmp_path)), "confirmed": False}
        )
        confirmation_id = result1.metadata["confirmation_id"]
        
        import time
        time.sleep(0.1)
        
        # Step 2: Try to confirm expired
        result2 = tools.execute(
            "file_delete",
            {
                "path": str(test_file.relative_to(tmp_path)),
                "confirmed": True,
                "confirmation_id": confirmation_id
            }
        )
        
        # Assert
        assert result2.status == "error"
        assert "过期" in result.result or "expired" in result.result.lower()

    def test_file_delete_directory_recursive_count(self, tmp_path):
        """TC-L5-CONFIRM-005: 批量删除正确计算受影响文件数"""
        # Arrange
        from src.l5.l5_tools import ToolsCapabilities
        tools = ToolsCapabilities()
        
        # Create directory with multiple files
        test_dir = tmp_path / "documents" / "test_dir"
        test_dir.mkdir(parents=True)
        (test_dir / "file1.txt").write_text("content1")
        (test_dir / "file2.txt").write_text("content2")
        (test_dir / "subdir").mkdir()
        (test_dir / "subdir" / "file3.txt").write_text("content3")
        
        # Act
        result = tools.execute(
            "file_delete",
            {
                "path": str(test_dir.relative_to(tmp_path)),
                "confirmed": False,
                "recursive": True
            }
        )
        
        # Assert
        assert result.status == "confirmation_required"
        assert result.metadata["affected_count"] >= 3  # 3 files + dirs

    def test_file_delete_sandbox_path_validation(self, tmp_path):
        """file_delete 强制沙盒路径验证"""
        # Arrange
        from src.l5.l5_tools import ToolsCapabilities
        tools = ToolsCapabilities()
        
        # Act - try to delete without documents/ prefix
        result = tools.execute(
            "file_delete",
            {"path": "test.txt", "confirmed": False}
        )
        
        # Assert
        assert result.status == "error"
        assert "documents/" in result.result
```

- [ ] **Step 2: 运行测试确保失败（TDD Red）**

Run:
```bash
pytest src/l5/tests/test_confirmation.py::TestFileDeleteTool -v
```

Expected: 6 个测试全部 FAIL（ToolNotFoundError: file_delete）

- [ ] **Step 3: 在 ToolsCapabilities 中集成 file_delete**

```python
# src/l5/l5_tools.py - 修改 ToolsCapabilities 类

class ToolsCapabilities(ToolsInterface):
    """L5 implementation - Tools and capabilities management."""

    def __init__(self, runtime: RuntimeInterface = None):
        self.runtime = runtime or RuntimeEnvironment()
        self.registry = ToolRegistry()
        self.validator = ParameterValidator()
        self.context_builder = ToolContextBuilder()
        # 新增：确认管理器
        self.confirmation_manager = ConfirmationManager()

    def execute(self, action_name: str, params: Dict[str, Any],
                user_permissions: List[str] = None, timeout: int = 30) -> Observation:
        """Execute a tool."""
        # 现有代码...
        
        # Execute
        if action_name == "python_repl":
            return self._execute_python(params, timeout)
        elif action_name == "calculator":
            return self._execute_calculator(params)
        elif action_name == "search_web":
            return self._execute_search(params)
        elif action_name == "file_reader":
            return self._execute_file_read(params)
        elif action_name == "file_writer":
            return self._execute_file_write(params)
        # 新增：file_delete
        elif action_name == "file_delete":
            return self._execute_file_delete(params)
        elif action_name == "terminal":
            return self._execute_terminal(params, timeout)
        else:
            # Check for custom handler
            if tool.handler:
                return tool.handler(params)
            raise ToolNotFoundError(f"Execution logic not implemented for '{action_name}'")

    # 现有方法保持不变...

    # ===== 新增：file_delete 执行方法 =====
    
    def _execute_file_delete(self, params: Dict) -> Observation:
        """Execute file delete with confirmation mechanism.
        
        Flow:
        1. First call (confirmed=False or missing): Return confirmation_required
        2. Second call (confirmed=True + valid confirmation_id): Execute delete
        """
        import os
        import time
        from src.core.exceptions import (
            ConfirmationRequiredError, ConfirmationExpiredError, InvalidConfirmationError
        )
        
        path = params.get("path", "")
        confirmed = params.get("confirmed", False)
        confirmation_id = params.get("confirmation_id")
        recursive = params.get("recursive", False)
        
        # Validate sandbox path first
        path_validation = self.validator.validate_sandbox_path(path)
        if not path_validation.valid:
            return Observation(
                status="error",
                result=f"路径验证失败: {'; '.join(path_validation.errors)}",
                execution_time=0.0,
                metadata={"path": path}
            )
        
        # Resolve full path
        try:
            full_path = self.validator.sanitize_path(path)
        except ValidationError as e:
            return Observation(
                status="error",
                result=str(e),
                execution_time=0.0,
                metadata={"path": path}
            )
        
        # Check if file/directory exists
        if not os.path.exists(full_path):
            return Observation(
                status="error",
                result=f"文件或目录不存在: {path}",
                execution_time=0.0,
                metadata={"path": path}
            )
        
        if not confirmed:
            # First call: Create pending operation and request confirmation
            affected_count = self._count_affected_files(full_path, recursive)
            
            new_confirmation_id = self.confirmation_manager.create_pending(
                "file_delete", params
            )
            
            return Observation(
                status="confirmation_required",
                result=f"确定要删除《{path}》吗？该操作不可恢复。\n将影响 {affected_count} 个文件/目录。",
                execution_time=0.0,
                metadata={
                    "confirmation_id": new_confirmation_id,
                    "affected_count": affected_count,
                    "expires_in": 300
                }
            )
        
        # Second call: Confirm and execute
        if not confirmation_id:
            return Observation(
                status="error",
                result="缺少 confirmation_id，请提供确认 ID",
                execution_time=0.0,
                metadata={"path": path}
            )
        
        try:
            # Verify and consume the pending operation
            pending = self.confirmation_manager.confirm_and_consume(confirmation_id)
            
            # Verify params match (anti-tampering)
            if pending.params.get("path") != path:
                return Observation(
                    status="error",
                    result="参数不匹配，请重新发起删除请求",
                    execution_time=0.0,
                    metadata={"path": path}
                )
            
            # Execute delete
            start_time = time.time()
            affected_count = self._count_affected_files(full_path, recursive)
            
            if os.path.isfile(full_path):
                os.remove(full_path)
            elif os.path.isdir(full_path):
                if recursive:
                    import shutil
                    shutil.rmtree(full_path)
                else:
                    os.rmdir(full_path)
            
            execution_time = time.time() - start_time
            
            return Observation(
                status="success",
                result=f"已成功删除 {path}（共 {affected_count} 个文件/目录）",
                execution_time=execution_time,
                metadata={
                    "path": path,
                    "affected_count": affected_count
                }
            )
            
        except InvalidConfirmationError:
            return Observation(
                status="error",
                result="确认 ID 无效或已过期，请重新发起删除请求",
                execution_time=0.0,
                metadata={"path": path, "expired": True}
            )
    
    def _count_affected_files(self, path: str, recursive: bool) -> int:
        """Count affected files/directories for deletion."""
        import os
        if os.path.isfile(path):
            return 1
        elif os.path.isdir(path):
            if recursive:
                count = 0
                for root, dirs, files in os.walk(path):
                    count += len(files) + len(dirs)
                return count + 1  # Include the directory itself
            else:
                return 1
        return 0
```

- [ ] **Step 4: 在 ToolRegistry 中注册 file_delete 工具**

```python
# src/l5/l5_tools.py - 在 ToolRegistry._register_builtin_tools 中添加

    def _register_builtin_tools(self):
        """Register built-in tools."""
        builtins = {
            # 现有工具...
            "file_reader": Tool(...),
            "file_writer": Tool(...),
            # 新增：file_delete
            "file_delete": Tool(
                name="file_delete",
                description="删除文件或目录。⚠️ 高危操作，需要二次确认。",
                parameters={
                    "path": {
                        "type": "string",
                        "description": "要删除的文件或目录路径（必须以 documents/ 开头）",
                        "required": True
                    },
                    "confirmed": {
                        "type": "boolean",
                        "description": "是否已确认删除（首次调用不传或传 false）",
                        "required": False,
                        "default": False
                    },
                    "confirmation_id": {
                        "type": "string",
                        "description": "确认 ID（confirmed=true 时必填）",
                        "required": False
                    },
                    "recursive": {
                        "type": "boolean",
                        "description": "是否递归删除目录",
                        "required": False,
                        "default": False
                    }
                },
                required_permission=None
            ),
            "terminal": Tool(...),
        }
```

- [ ] **Step 5: 更新 l5/__init__.py 导出**

```python
# src/l5/__init__.py - 更新导出

from src.l5.l5_tools import (
    ToolsCapabilities,
    Tool,
    ToolRegistry,
    ParameterValidator,
    ToolContextBuilder,
    ValidationResult
)
from src.l5.confirmation_manager import (
    ConfirmationManager,
    PendingOperation
)

__all__ = [
    'ToolsCapabilities',
    'Tool',
    'ToolRegistry',
    'ParameterValidator',
    'ToolContextBuilder',
    'ValidationResult',
    'ConfirmationManager',  # 新增
    'PendingOperation',      # 新增
]
```

- [ ] **Step 6: 运行测试确保通过（TDD Green）**

Run:
```bash
pytest src/l5/tests/test_confirmation.py -v
```

Expected: 12 个测试全部 PASS

- [ ] **Step 7: 运行所有 L5 测试确保无回归**

Run:
```bash
pytest src/l5/tests/ -v
```

Expected: 24 个测试全部 PASS（12 现有 + 12 新增）

- [ ] **Step 8: Commit**

```bash
git add src/l5/
git commit -m "feat(l5): implement file_delete tool with confirmation mechanism"
```

---

## Task 5: 更新测试文档

**Files:**
- Modify: `src/l5/tests/README.md`

**Context:** 更新测试文档，说明新增测试文件和依赖。

- [ ] **Step 1: 更新 README.md**

```markdown
# src/l5/tests/README.md

## L5 能力抽象层测试

本目录包含 L5 Tools & Capabilities 层的所有单元测试。

## 测试文件列表

| 文件 | 用途 | 依赖 | 状态 |
|------|------|------|------|
| `test_l5.py` | L5 核心功能测试（12 个） | 无 | ✅ 已完成 |
| `test_confirmation.py` | 二次确认机制测试（6 个） | 无 | ✅ 已完成 |
| `test_path_validation.py` | 沙盒路径验证测试（5 个） | 无 | ✅ 已完成 |

## 依赖清单

```bash
# 无需额外依赖，使用项目标准依赖
pip install -r requirements.txt
```

## 运行方法

```bash
# 运行所有 L5 测试
pytest src/l5/tests/ -v

# 运行特定测试文件
pytest src/l5/tests/test_l5.py -v
pytest src/l5/tests/test_confirmation.py -v
pytest src/l5/tests/test_path_validation.py -v

# 运行特定测试
pytest src/l5/tests/test_confirmation.py::TestFileDeleteTool::test_file_delete_first_request_returns_confirmation_required -v
```

## 测试覆盖

- **工具执行**: python_repl, calculator, search_web, file_reader, file_writer, file_delete, terminal
- **确认机制**: 首次请求、确认执行、过期处理、无效 ID 处理、批量删除计数
- **路径验证**: 沙盒前缀、目录遍历、绝对路径防护

## 注意事项

- 所有测试使用 `tmp_path` fixture 创建隔离的临时目录
- file_delete 测试需要文件系统写权限
- 确认过期测试使用 0 秒 TTL 加速测试
```

- [ ] **Step 2: Commit**

```bash
git add src/l5/tests/README.md
git commit -m "docs(l5): update test documentation for new tests"
```

---

## Task 6: 最终验证

**Files:** 所有修改的文件

- [ ] **Step 1: 运行完整测试套件**

Run:
```bash
pytest src/l5/tests/ -v
```

Expected:
```
============================= test session starts ==============================
platform win32 -- Python 3.13.5
pytest-8.3.4

collected 24 items

src/l5/tests/test_l5.py::TestToolsCapabilities::test_tool_execution_success PASSED
...
src/l5/tests/test_confirmation.py::TestConfirmationManager::test_create_pending_returns_confirmation_id PASSED
...
src/l5/tests/test_path_validation.py::TestSandboxPathValidation::test_valid_documents_path_passes PASSED
...

============================== 24 passed in X.XXs ==============================
```

- [ ] **Step 2: 验证接口兼容**

Run:
```python
python -c "
from src.l5 import ToolsCapabilities, ConfirmationManager
tools = ToolsCapabilities()
print('execute:', hasattr(tools, 'execute'))
print('get_available_tools:', hasattr(tools, 'get_available_tools'))
print('file_delete in tools:', 'file_delete' in [t.name for t in tools.registry.list_tools()])
print('All OK')
"
```

Expected:
```
execute: True
get_available_tools: True
file_delete in tools: True
All OK
```

- [ ] **Step 3: 最终 Commit**

```bash
git add -A
git commit -m "feat(l5): complete file_delete tool with confirmation - all tests passing"
```

---

## Spec Coverage Checklist

对照设计文档验证所有功能已实现：

- [ ] **ConfirmationManager** - 内存存储、TTL、自动清理
- [ ] **PendingOperation** - 数据类定义
- [ ] **异常类型** - ConfirmationRequiredError, ConfirmationExpiredError, InvalidConfirmationError
- [ ] **validate_sandbox_path** - 强制 documents/ 前缀
- [ ] **file_delete 工具** - 二次确认流程
- [ ] **_count_affected_files** - 批量删除计数
- [ ] **路径验证** - 目录遍历防护、绝对路径禁止
- [ ] **测试覆盖** - 12 个新增测试
- [ ] **文档更新** - README.md

---

**Plan complete and saved to `docs/superpowers/plans/2026-04-12-l5-file-delete.md`.**

**Two execution options:**

1. **Subagent-Driven (recommended)** - Dispatch a fresh subagent per task, review between tasks
2. **Inline Execution** - Execute tasks in this session using executing-plans

**Which approach would you like to use?**

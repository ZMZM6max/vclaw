# L5 能力抽象层增强设计文档

**日期**: 2026-04-12  
**主题**: L5 ToolsCapabilities 完整实现 - file_delete 二次确认机制  
**作者**: Claude Code  
**状态**: 已批准

---

## 1. 设计目标

根据 `docs/L5_ToolsCapabilities.xml` 规范，完整实现 L5 层的能力抽象功能，重点完成：

1. **file_delete 高危操作工具** - 实现二次确认机制
2. **增强路径安全验证** - 强制沙盒路径前缀 (`documents/`)
3. **批量删除检测** - 预览受影响文件数量
4. **完整的测试覆盖** - TDD 开发模式

---

## 2. 架构方法

### 2.1 选择的方法：内部状态机（方法 A）

L5 内部维护待确认操作队列，封装确认机制的复杂性，L3 层无需特殊处理。

```
L3 → L5.execute(file_delete, {path: "a.txt"})
     → 创建 PendingOperation
     → 返回 confirmation_required 状态

L3 → L5.execute(file_delete, {path: "a.txt", confirmed: true, confirmation_id: "xxx"})
     → 验证并执行删除
     → 返回 success 状态
```

### 2.2 设计理由

- 符合 XML 规范中 L5 负责"高危操作二次确认"的设计
- 状态管理内聚在 L5，职责清晰
- 与现有 `ToolsCapabilities` 类结构融合良好
- 不过度设计，满足当前需求

---

## 3. 组件设计

### 3.1 ConfirmationManager（新增）

管理需要二次确认的高危操作。

```python
@dataclass
class PendingOperation:
    confirmation_id: str      # UUID 唯一标识
    tool_name: str            # 工具名称
    params: Dict              # 原始参数
    created_at: float         # 创建时间戳
    expires_at: float         # 过期时间戳（默认 300 秒）

class ConfirmationManager:
    _pending: Dict[str, PendingOperation]  # 内存存储
    DEFAULT_TTL: int = 300  # 5 分钟

    def create_pending(tool_name: str, params: Dict) -> str:
        """创建待确认记录，返回 confirmation_id"""

    def get_pending(confirmation_id: str) -> Optional[PendingOperation]:
        """获取有效的待确认操作（自动清理过期记录）"""

    def confirm_and_consume(confirmation_id: str) -> PendingOperation:
        """确认并消费记录，返回原始参数用于执行"""

    def _cleanup_expired():
        """清理过期记录（每次操作时自动调用）"""
```

### 3.2 file_delete 工具定义

```python
Tool(
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
    }
)
```

### 3.3 执行流程

#### 首次调用（确认请求）

```python
def _execute_file_delete(params: Dict) -> Observation:
    path = params["path"]
    confirmed = params.get("confirmed", False)

    if not confirmed:
        # 1. 路径验证
        validate_sandbox_path(path)

        # 2. 计算受影响文件数
        affected_count = _count_affected_files(path, recursive)

        # 3. 创建待确认记录
        confirmation_id = confirmation_manager.create_pending(
            "file_delete", params
        )

        # 4. 返回确认请求
        return Observation(
            status="confirmation_required",
            result=f"确定要删除《{path}》吗？该操作不可恢复。\n将影响 {affected_count} 个文件/目录。",
            execution_time=0.0,
            metadata={
                "confirmation_id": confirmation_id,
                "affected_count": affected_count,
                "expires_in": 300
            }
        )
```

#### 二次调用（确认执行）

```python
    # confirmed = True
    confirmation_id = params["confirmation_id"]

    # 1. 验证 confirmation_id
    pending = confirmation_manager.get_pending(confirmation_id)
    if not pending:
        raise ConfirmationExpiredError("确认已过期或无效")

    # 2. 验证参数匹配（防篡改）
    if pending.params["path"] != path:
        raise InvalidConfirmationError("参数不匹配")

    # 3. 执行删除
    confirmation_manager.confirm_and_consume(confirmation_id)
    _perform_delete(path, recursive)

    return Observation(
        status="success",
        result=f"已成功删除 {path}",
        execution_time=execution_time,
        metadata={"path": path, "affected_count": affected_count}
    )
```

### 3.4 批量删除检测

```python
def _count_affected_files(path: str, recursive: bool) -> int:
    """计算受影响文件/目录数量"""
    if os.path.isfile(path):
        return 1
    elif os.path.isdir(path) and recursive:
        count = 0
        for root, dirs, files in os.walk(path):
            count += len(files) + len(dirs)
        return count + 1  # 包括目录本身
    elif os.path.isdir(path):
        return 1  # 仅目录本身
    return 0  # 路径不存在
```

---

## 4. 路径安全增强

### 4.1 沙盒路径验证规则

根据 XML 规范，文件操作工具必须满足：

| 规则 | 优先级 | 说明 |
|------|--------|------|
| `documents/` 前缀 | Critical | 路径必须以 `documents/` 开头 |
| 目录遍历防护 | Critical | 禁止包含 `..` |
| 绝对路径禁止 | High | 禁止 `/` 或 `C:\` 开头 |
| 系统目录防护 | High | 禁止 `/etc`, `/sys` 等 |

### 4.2 增强的 ParameterValidator

```python
class ParameterValidator:
    SANDBOX_ROOT = "documents/"

    @staticmethod
    def validate_sandbox_path(path: str) -> ValidationResult:
        """验证路径是否符合沙盒规则"""
        errors = []

        # 必须以 documents/ 开头
        if not path.startswith("documents/"):
            errors.append("路径必须在沙盒范围内，必须以 'documents/' 开头")

        # 禁止目录遍历
        if ".." in path:
            errors.append("检测到目录遍历攻击，路径包含非法字符 '..'")

        # 禁止绝对路径
        if path.startswith("/") or re.match(r'^[A-Za-z]:\\', path):
            errors.append("禁止使用绝对路径")

        # 保留现有的 DANGEROUS_PATH_PATTERNS 检查
        for pattern in DANGEROUS_PATH_PATTERNS:
            if re.search(pattern, path, re.IGNORECASE):
                errors.append(f"路径包含非法模式: {pattern}")

        return ValidationResult(valid=len(errors) == 0, errors=errors)
```

### 4.3 路径转换说明

L3 层负责将用户友好路径转换为沙盒路径：

| 用户输入 | 转换后路径 | 说明 |
|----------|-----------|------|
| `桌面/文件.txt` | `documents/desktop/文件.txt` | 中文别名映射 |
| `downloads/report.pdf` | `documents/downloads/report.pdf` | 子目录映射 |
| `test.py` | 验证失败 | 缺少 documents/ 前缀 |

如果 L3 未正确转换，L5 验证失败时返回清晰错误信息。

---

## 5. 异常设计

### 5.1 新增异常类型

```python
# src/core/exceptions.py

class ConfirmationRequiredError(VClawException):
    """需要用户确认（状态类异常，非错误）"""
    def __init__(self, message: str, confirmation_id: str, affected_count: int = 1):
        super().__init__(message)
        self.confirmation_id = confirmation_id
        self.affected_count = affected_count

class ConfirmationExpiredError(VClawException):
    """确认已过期"""
    pass

class InvalidConfirmationError(VClawException):
    """确认 ID 无效或已被使用"""
    pass
```

### 5.2 异常转换策略

L5 内部使用异常，对外统一返回 `Observation`：

```python
def execute(self, action_name: str, params: Dict, ...) -> Observation:
    try:
        return self._do_execute(action_name, params, ...)
    except ConfirmationRequiredError as e:
        return Observation(
            status="confirmation_required",
            result=f"确定要删除吗？将影响 {e.affected_count} 个文件。",
            metadata={"confirmation_id": e.confirmation_id, ...}
        )
    except ConfirmationExpiredError:
        return Observation(status="error", result="确认已过期...")
    except InvalidConfirmationError:
        return Observation(status="error", result="确认 ID 无效...")
```

这样 L3 层可以统一处理 `Observation.status`，无需特殊 try-catch。

---

## 6. 测试设计

### 6.1 测试覆盖表

| 测试文件 | 测试 ID | 测试名称 | 验证内容 |
|----------|---------|----------|----------|
| test_confirmation.py | TC-L5-CONFIRM-001 | 首次删除请求创建待确认记录 | `confirmed=false` 返回 `confirmation_id` |
| test_confirmation.py | TC-L5-CONFIRM-002 | 确认后执行删除 | `confirmed=true` + 有效 ID 删除成功 |
| test_confirmation.py | TC-L5-CONFIRM-003 | 无效 confirmation_id 被拒绝 | 错误 ID 返回错误状态 |
| test_confirmation.py | TC-L5-CONFIRM-004 | 过期确认被拒绝 | 超时后确认返回过期错误 |
| test_confirmation.py | TC-L5-CONFIRM-005 | 批量删除影响计数 | 目录删除正确计算文件数 |
| test_path_validation.py | TC-L5-PATH-002 | 沙盒路径前缀验证 | 非 `documents/` 路径被拒绝 |
| test_path_validation.py | TC-L5-PATH-003 | 目录遍历防护 | 包含 `..` 的路径被拒绝 |

### 6.2 测试示例

```python
# test_confirmation.py
class TestFileDeleteConfirmation:
    def test_first_delete_request_creates_pending(self):
        """TC-L5-CONFIRM-001: 首次删除请求创建待确认记录"""
        tools = ToolsCapabilities()

        result = tools.execute(
            "file_delete",
            {"path": "documents/test.txt", "confirmed": False}
        )

        assert result.status == "confirmation_required"
        assert "confirmation_id" in result.metadata
        assert result.metadata["affected_count"] == 1
        assert "确定要删除" in result.result

    def test_confirm_and_execute_delete(self, tmp_path):
        """TC-L5-CONFIRM-002: 确认后执行删除"""
        # 创建测试文件
        test_file = tmp_path / "documents" / "test.txt"
        test_file.parent.mkdir(parents=True)
        test_file.write_text("test content")

        tools = ToolsCapabilities()

        # 第一步：发起删除请求
        result1 = tools.execute(
            "file_delete",
            {"path": str(test_file.relative_to(tmp_path)), "confirmed": False}
        )
        confirmation_id = result1.metadata["confirmation_id"]

        # 第二步：确认删除
        result2 = tools.execute(
            "file_delete",
            {
                "path": str(test_file.relative_to(tmp_path)),
                "confirmed": True,
                "confirmation_id": confirmation_id
            }
        )

        assert result2.status == "success"
        assert not test_file.exists()
```

### 6.3 测试环境要求

- 使用 `tmp_path` pytest fixture 创建隔离测试目录
- 模拟时间流逝测试 TTL 过期（使用 `freezegun` 或手动修改时间）
- Mock `RuntimeInterface` 测试 L5 独立逻辑

---

## 7. 目录结构

### 7.1 最终文件布局

```
src/l5/
├── __init__.py                  # 包导出
├── l5_tools.py                  # 现有：主类增强
├── confirmation_manager.py      # 新增：待确认操作管理
└── tests/
    ├── __init__.py
    ├── test_l5.py               # 现有测试（12 个）
    ├── test_confirmation.py     # 新增（5 个）
    ├── test_path_validation.py  # 新增（2 个）
    └── README.md                # 更新文档
```

### 7.2 接口兼容性

所有现有接口保持不变：

```python
# 现有接口不变
ToolsCapabilities.execute(action_name, params, user_permissions, timeout) -> Observation
ToolsCapabilities.get_available_tools(user_permissions) -> List[Dict]
ToolsCapabilities.list_tools() -> List[Dict[str, Any]]
```

新增 `file_delete` 工具会出现在 `get_available_tools()` 返回列表中。

---

## 8. 数据流示例

### 8.1 文件删除完整流程

```
用户: "删除 documents/test.txt"
  │
  ▼
L3: 识别意图 → 生成 AgentAction(
    action="file_delete",
    action_input={"path": "documents/test.txt"}
)
  │
  ▼
L5.execute("file_delete", {"path": "documents/test.txt"})
  ├── 验证路径: ✅ documents/test.txt
  ├── 计算影响: 1 个文件
  ├── 创建待确认记录: confirmation_id="uuid-xxx"
  └── 返回 Observation(
      status="confirmation_required",
      result="确定要删除《documents/test.txt》吗？...",
      metadata={"confirmation_id": "uuid-xxx", "affected_count": 1}
  )
  │
  ▼
L3: 检测到 confirmation_required → 回复用户请求确认
  │
  ▼
用户: "确认"
  │
  ▼
L3: 添加 confirmed=true 和 confirmation_id → 再次调用 L5
  │
  ▼
L5.execute("file_delete", {
    "path": "documents/test.txt",
    "confirmed": True,
    "confirmation_id": "uuid-xxx"
})
  ├── 验证 confirmation_id: ✅ 有效
  ├── 验证参数匹配: ✅
  ├── 执行删除: ✅
  └── 返回 Observation(status="success", result="已成功删除...")
  │
  ▼
L3: 返回成功结果给用户
```

---

## 9. 关键决策记录

| 决策 | 选择 | 理由 |
|------|------|------|
| 状态管理方式 | 内部状态机 | 符合六层架构职责划分，L3 无需特殊处理 |
| 存储方式 | 内存 Dict | 简单高效，无需持久化（短期确认） |
| TTL | 300 秒 | 平衡安全性和用户体验 |
| confirmation_id 格式 | UUID | 难以猜测，防篡改 |
| 异常处理 | 内部异常转 Observation | L3 统一处理，接口一致 |
| 路径前缀 | 强制 `documents/` | 符合 XML 规范安全要求 |

---

## 10. XML 规范全覆盖对照表

### 10.1 组件实现对照

| XML 组件 | 实现类/方法 | 状态 | 说明 |
|----------|------------|------|------|
| **ToolRegistry** | `ToolRegistry` | ✅ 完整 | `register()`, `unregister()`, `get()`, `list_tools()` |
| **ParameterValidator** | `ParameterValidator` | 🔄 增强 | 新增 `validate_sandbox_path()` 沙盒路径验证 |
| **ToolExecutor** | `_execute_*` 方法 | ✅ 完整 | 各工具执行逻辑封装在 `ToolsCapabilities` |
| **ResultFormatter** | `Observation` 构造 | ✅ 完整 | 统一格式化结果为 Observation 对象 |
| **ToolMetadataManager** | `get_available_tools()`, `get_tools_with_descriptions()` | ✅ 完整 | OpenAI Function Calling 格式支持 |
| **ConfirmationManager** | `ConfirmationManager` (新增) | 🔄 新增 | 高危操作二次确认状态管理 |

### 10.2 工具实现对照

| XML 工具 | 实现方法 | 状态 | 说明 |
|----------|---------|------|------|
| **python_repl** | `_execute_python()` | ✅ 完整 | 调用 L6 Runtime 执行 Python 代码 |
| **search_web** | `_execute_search()` | ✅ 完整 | Mock 实现，预留真实搜索接口 |
| **file_read** | `_execute_file_read()` | ✅ 完整 | 支持沙盒路径验证 |
| **file_write** | `_execute_file_write()` | ✅ 完整 | 支持沙盒路径验证 |
| **file_delete** | `_execute_file_delete()` (新增) | 🔄 新增 | **二次确认机制完整实现** |
| **terminal** | `_execute_terminal()` | ✅ 完整 | 命令白名单验证 |
| **calculator** | `_execute_calculator()` | ✅ 完整 | 安全表达式求值 |

### 10.3 参数验证规则对照

| XML 规则 | 实现位置 | 状态 | 说明 |
|----------|---------|------|------|
| **参数类型匹配** | `ParameterValidator.validate()` | ✅ 完整 | string/integer/boolean 类型检查 |
| **必需字段检查** | `ParameterValidator.validate()` | ✅ 完整 | required 字段验证 |
| **值范围限制** | `ParameterValidator.validate()` | ✅ 完整 | maxLength 等约束 |
| **字符串长度限制** | `ParameterValidator.validate()` | ✅ 完整 | 最大长度验证 |
| **沙盒路径前缀检查** | `validate_sandbox_path()` (新增) | 🔄 新增 | **强制 `documents/` 前缀** |
| **目录遍历防护** | `DANGEROUS_PATH_PATTERNS` | ✅ 完整 | 禁止 `..` 等模式 |
| **系统敏感目录防护** | `DANGEROUS_PATH_PATTERNS` | ✅ 完整 | 禁止 `/etc`, `/sys` 等 |
| **绝对路径防护** | `validate_sandbox_path()` (新增) | 🔄 新增 | **禁止绝对路径** |
| **高危操作二次确认** | `ConfirmationManager` (新增) | 🔄 新增 | **file_delete 确认机制** |

### 10.4 接口规范对照

| XML 接口 | 实现方法 | 状态 | 说明 |
|----------|---------|------|------|
| `execute(action_name, params, timeout)` | `ToolsCapabilities.execute()` | ✅ 完整 | 主执行接口，返回 Observation |
| `get_available_tools()` | `ToolsCapabilities.get_available_tools()` | ✅ 完整 | 返回 OpenAI Function 格式 |
| **新增参数支持** | `user_permissions` | ✅ 保留 | 向后兼容，当前不检查权限 |

### 10.5 异常类型对照

| XML 异常 | 实现类 | 状态 | 说明 |
|----------|-------|------|------|
| `ToolNotFoundError` | `ToolNotFoundError` | ✅ 完整 | 工具不存在 |
| `ValidationError` | `ValidationError` | ✅ 完整 | 参数验证失败 |
| `ExecutionTimeoutError` | `ExecutionTimeoutError` | ✅ 完整 | 执行超时 |
| `ExecutionError` | 转为 Observation | ✅ 完整 | 工具执行失败 |
| `ConfirmationRequiredError` (新增) | `ConfirmationRequiredError` | 🔄 新增 | **需要确认** |
| `ConfirmationExpiredError` (新增) | `ConfirmationExpiredError` | 🔄 新增 | **确认过期** |
| `InvalidConfirmationError` (新增) | `InvalidConfirmationError` | 🔄 新增 | **确认无效** |

---

## 11. 验收标准

### 11.1 功能验收

- [ ] **file_delete** 工具可用并返回正确格式的确认请求
- [ ] 二次确认机制正确执行删除操作
- [ ] 过期确认正确拒绝并提示重新发起
- [ ] 批量删除正确计算并显示受影响文件数
- [ ] 所有路径验证规则正确执行（沙盒前缀、目录遍历等）

### 11.2 组件验收

- [ ] **ToolRegistry** - 7 个工具全部注册并可发现
- [ ] **ParameterValidator** - 所有验证规则正确执行
- [ ] **ConfirmationManager** - TTL、过期清理、防篡改正常工作
- [ ] **ToolMetadataManager** - OpenAI Function Calling 格式正确

### 11.3 接口验收

- [ ] `execute()` - 所有 7 个工具可正常执行
- [ ] `get_available_tools()` - 返回完整工具列表（含 file_delete）
- [ ] `list_tools()` - 返回完整工具定义

### 11.4 测试验收

- [ ] 现有 12 个测试用例全部通过（回归测试）
- [ ] 新增 7 个测试用例全部通过（file_delete + 路径验证）
- [ ] 总测试数：19 个全部通过

### 11.5 文档验收

- [ ] `src/l5/tests/README.md` 更新测试文档
- [ ] `src/l5/__init__.py` 导出新增类
- [ ] 代码注释完整（docstring）

---

**设计批准**: 用户已确认所有设计部分  
**XML 规范覆盖**: ✅ 100% 全覆盖（7 个工具、5 个组件、所有验证规则）  
**下一步**: 使用 writing-plans skill 创建实施计划

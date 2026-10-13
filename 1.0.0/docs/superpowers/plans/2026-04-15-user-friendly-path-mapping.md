# 用户友好路径智能映射系统实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 L5 新建 PathMapper 服务，统一把 "桌面"、"下载" 等中文/自然语言路径解析为真实操作系统路径，并配合 PermissionManager 实现分级权限控制；同时更新 L3 提示词移除硬编码映射。

**Architecture:** PathMapper 负责路径语义解析，PermissionManager 负责真实路径区域的分级权限，L5 工具执行前统一调用 PathMapper 拦截转换，L3 提示词简化为自然语言路径引导。`documents/` 开头的旧路径保持向后兼容。

**Tech Stack:** Python, `pathlib`, `os.path.expanduser`, `platform`

---

## 文件结构

| 文件 | 职责 |
|------|------|
| `src/l5/path_mapper.py` | **新建** PathMapper：路径别名解析、真实 OS 路径映射 |
| `src/l5/tests/test_path_mapper.py` | **新建** PathMapper 单元测试 |
| `src/l5/permissions.py` | 为真实路径区域（Desktop/Downloads/Documents 等）添加默认权限规则 |
| `src/l5/tests/test_permissions.py` | 增加真实路径权限测试 |
| `src/l5/l5_tools.py` | 在 file_reader/file_writer/file_delete/terminal 执行前集成 PathMapper |
| `src/l5/tests/test_l5.py` | 更新集成测试 |
| `src/l3/l3_orchestration.py` | 更新系统提示词，移除硬编码 `documents/desktop` 映射 |
| `src/l3/tests/test_l3.py` | 移除或更新旧的路径处理测试断言 |
| `src/l5/tests/README.md` | 添加 path_mapper 测试文档 |
| `docs/L3_Orchestration.xml` | 同步更新架构文档中的 L3 提示词 |
| `CLAUDE.md` | 同步更新 L3 提示词文档 |

---

### Task 1: PathMapper 核心实现

**Files:**
- Create: `src/l5/path_mapper.py`
- Test: `src/l5/tests/test_path_mapper.py`

- [ ] **Step 1: Write the failing test**

Create `src/l5/tests/test_path_mapper.py`:

```python
import sys
from pathlib import Path
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from src.l5.path_mapper import PathMapper, PathMappingError


def test_resolve_desktop_alias():
    mapper = PathMapper()
    result = mapper.resolve("桌面/周会提醒.txt")
    assert result.endswith("Desktop\\周会提醒.txt") or result.endswith("Desktop/周会提醒.txt")


def test_resolve_downloads_alias():
    mapper = PathMapper()
    result = mapper.resolve("downloads/report.pdf")
    assert result.endswith("Downloads\\report.pdf") or result.endswith("Downloads/report.pdf")


def test_resolve_documents_alias():
    mapper = PathMapper()
    result = mapper.resolve("文档/笔记.md")
    assert result.endswith("Documents\\笔记.md") or result.endswith("Documents/笔记.md")


def test_resolve_single_filename_defaults_to_documents():
    mapper = PathMapper()
    result = mapper.resolve("test.txt")
    assert result.endswith("Documents\\test.txt") or result.endswith("Documents/test.txt")


def test_resolve_absolute_path_unchanged():
    mapper = PathMapper()
    result = mapper.resolve("C:\\Windows\\System32\\notepad.exe")
    assert result == "C:\\Windows\\System32\\notepad.exe"


def test_resolve_documents_prefix_sandbox():
    mapper = PathMapper()
    result = mapper.resolve("documents/sandbox/file.txt")
    assert "documents" in result.lower()
    assert result.endswith("sandbox\\file.txt") or result.endswith("sandbox/file.txt")


def test_resolve_unknown_raises():
    mapper = PathMapper()
    try:
        mapper.resolve("unknown_folder/file.txt")
        assert False, "Should raise PathMappingError"
    except PathMappingError:
        pass
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest src/l5/tests/test_path_mapper.py -v
```

Expected: FAIL with "ModuleNotFoundError: No module named 'src.l5.path_mapper'"

- [ ] **Step 3: Write minimal implementation**

Create `src/l5/path_mapper.py`:

```python
"""Path mapper for resolving user-friendly paths to real OS paths."""
import os
import platform
from pathlib import Path
from typing import Dict, Optional


class PathMappingError(Exception):
    """Raised when a path cannot be resolved."""
    pass


class PathMapper:
    """Maps natural language paths to real operating system paths.

    Examples:
        >>> mapper = PathMapper()
        >>> mapper.resolve("桌面/文件.txt")
        'C:\\Users\\<user>\\Desktop\\文件.txt'
        >>> mapper.resolve("documents/sandbox/file.txt")
        'E:\\...\\vclaw\\documents\\sandbox\\file.txt'
    """

    ALIASES: Dict[str, str] = {
        "桌面": "~/Desktop",
        "desktop": "~/Desktop",
        "下载": "~/Downloads",
        "downloads": "~/Downloads",
        "文档": "~/Documents",
        "documents": "~/Documents",
        "图片": "~/Pictures",
        "pictures": "~/Pictures",
        "音乐": "~/Music",
        "music": "~/Music",
        "视频": "~/Videos",
        "videos": "~/Videos",
    }

    def __init__(self, sandbox_documents_root: Optional[str] = None):
        """Initialize PathMapper.

        Args:
            sandbox_documents_root: Base directory for 'documents/' backward compatibility.
                                   Defaults to project root.
        """
        if sandbox_documents_root:
            self.sandbox_root = Path(sandbox_documents_root).resolve()
        else:
            # Default to project root (parent of src/)
            self.sandbox_root = Path(__file__).resolve().parent.parent.parent

    def resolve(self, path: str) -> str:
        """Resolve a user-friendly path to a real OS path.

        Resolution order:
        1. Absolute path -> return as-is
        2. Starts with 'documents/' -> sandbox root
        3. Matches known alias -> real OS directory
        4. Single filename -> ~/Documents/filename
        5. Unknown -> raise PathMappingError
        """
        path = path.strip()

        # 1. Absolute path
        if self._is_absolute(path):
            return path

        # Normalize separators
        normalized = path.replace("\\", "/")
        first_segment = normalized.split("/")[0].lower()

        # 2. Backward-compatible sandbox paths
        if first_segment == "documents":
            relative = normalized[len("documents/"):] if normalized.startswith("documents/") else normalized[len("documents"):]
            relative = relative.lstrip("/")
            return str(self.sandbox_root / "documents" / relative)

        # 3. Alias mapping
        alias_target = self.ALIASES.get(first_segment)
        if alias_target:
            base = Path(alias_target).expanduser().resolve()
            remainder = "/".join(normalized.split("/")[1:])
            if remainder:
                return str(base / remainder)
            return str(base)

        # 4. Single filename -> default to Documents
        if "/" not in normalized and "\\" not in path:
            return str(Path("~/Documents").expanduser().resolve() / normalized)

        # 5. Unknown
        raise PathMappingError(f"无法解析路径: '{path}'。请使用已知别名（如桌面、下载、文档）或绝对路径。")

    @staticmethod
    def _is_absolute(path: str) -> bool:
        """Check if path is absolute on Windows, macOS, or Linux."""
        if len(path) >= 2 and path[1] == ":":
            return True
        if path.startswith("/") or path.startswith("\\"):
            return True
        return False
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest src/l5/tests/test_path_mapper.py -v
```

Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add src/l5/path_mapper.py src/l5/tests/test_path_mapper.py
git commit -m "feat(l5): add PathMapper for natural language path resolution"
```

---

### Task 2: PermissionManager 真实路径权限规则

**Files:**
- Modify: `src/l5/permissions.py`
- Test: `src/l5/tests/test_permissions.py`

- [ ] **Step 1: Write the failing test**

Add to `src/l5/tests/test_permissions.py` (create if not exists, otherwise append):

```python
def test_desktop_write_requires_ask():
    from src.l5.permissions import PermissionManager, PermissionRule, PermissionMode
    manager = PermissionManager()
    # Desktop write should be ASK
    result = manager.check_permission("file_writer", "C:\\Users\\Test\\Desktop\\file.txt")
    assert result.allowed is True
    assert result.mode == PermissionMode.ASK


def test_documents_read_auto_applied():
    from src.l5.permissions import PermissionManager, PermissionRule, PermissionMode
    manager = PermissionManager()
    result = manager.check_permission("file_reader", "C:\\Users\\Test\\Documents\\file.txt")
    assert result.allowed is True
    assert result.mode == PermissionMode.AUTO_APPLY


def test_unknown_absolute_path_defaults_to_ask():
    from src.l5.permissions import PermissionManager, PermissionRule, PermissionMode
    manager = PermissionManager()
    result = manager.check_permission("file_writer", "D:\\Random\\file.txt")
    assert result.allowed is True
    assert result.mode == PermissionMode.ASK
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest src/l5/tests/test_permissions.py::test_desktop_write_requires_ask -v
```

Expected: FAIL with AssertionError (currently returns AUTO_APPLY because there is no specific rule)

- [ ] **Step 3: Write minimal implementation**

Modify `src/l5/permissions.py`, find `PermissionManager.__init__` and add default rules.

If `__init__` currently has `_setup_default_rules()`, modify that method. If not, add it.

```python
    def __init__(self):
        """Initialize the permission manager."""
        self._rules: List[PermissionRule] = []
        self._default_mode = PermissionMode.ASK
        self._setup_default_rules()

    def _setup_default_rules(self):
        """Setup default permission rules for sandbox and real path security."""
        # Real Desktop: read auto, write/delete ask
        self.add_rule(PermissionRule("**/Desktop/**", PermissionMode.AUTO_APPLY, tools=["file_reader"]))
        self.add_rule(PermissionRule("**/Desktop/**", PermissionMode.ASK, tools=["file_writer", "file_delete", "terminal"]))

        # Real Downloads: read/write auto, delete ask
        self.add_rule(PermissionRule("**/Downloads/**", PermissionMode.AUTO_APPLY, tools=["file_reader", "file_writer"]))
        self.add_rule(PermissionRule("**/Downloads/**", PermissionMode.ASK, tools=["file_delete", "terminal"]))

        # Real Documents: read/write auto, delete ask
        self.add_rule(PermissionRule("**/Documents/**", PermissionMode.AUTO_APPLY, tools=["file_reader", "file_writer"]))
        self.add_rule(PermissionRule("**/Documents/**", PermissionMode.ASK, tools=["file_delete", "terminal"]))

        # Real Pictures/Music/Videos: read auto, write/delete ask
        for folder in ["Pictures", "Music", "Videos"]:
            self.add_rule(PermissionRule(f"**/{folder}/**", PermissionMode.AUTO_APPLY, tools=["file_reader"]))
            self.add_rule(PermissionRule(f"**/{folder}/**", PermissionMode.ASK, tools=["file_writer", "file_delete", "terminal"]))

        # Sandbox documents: allow auto-apply for most operations (legacy behavior)
        self.add_rule(PermissionRule("documents/**", PermissionMode.AUTO_APPLY, tools=["file_reader", "file_writer"]))
        self.add_rule(PermissionRule("documents/**", PermissionMode.ASK, tools=["file_delete", "terminal"]))

        # Config directory: read-only
        self.add_rule(PermissionRule("config/**", PermissionMode.READ_ONLY))

        # Deny system paths outside known folders (must be last)
        self.add_rule(PermissionRule("/System/**", PermissionMode.READ_ONLY))
        self.add_rule(PermissionRule("C:/Windows/**", PermissionMode.READ_ONLY))
        self.add_rule(PermissionRule("C:/Program Files/**", PermissionMode.READ_ONLY))
```

Note: If `_setup_default_rules` already exists in `src/l5/permissions.py`, carefully merge the above rules with existing ones, keeping the legacy `documents/**` rules.

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest src/l5/tests/test_permissions.py -v
```

Expected: all tests pass

- [ ] **Step 5: Commit**

```bash
git add src/l5/permissions.py src/l5/tests/test_permissions.py
git commit -m "feat(l5): add permission rules for real OS path areas"
```

---

### Task 3: 在 L5 工具执行中集成 PathMapper

**Files:**
- Modify: `src/l5/l5_tools.py`
- Test: `src/l5/tests/test_l5.py`

- [ ] **Step 1: Inspect current file operation implementations**

Open `src/l5/l5_tools.py` and find:
- `_execute_file_read`
- `_execute_file_write`
- `_execute_file_delete`
- `execute` method where terminal working_dir is handled

- [ ] **Step 2: Add PathMapper instance to ToolsCapabilities**

In `src/l5/l5_tools.py`, find `ToolsCapabilities.__init__` and add:

```python
from src.l5.path_mapper import PathMapper

class ToolsCapabilities:
    def __init__(self):
        # ... existing init code ...
        self.path_mapper = PathMapper()
```

If `__init__` already has many lines, add right after `self.validator = ParameterValidator()` or similar.

- [ ] **Step 3: Modify _execute_file_read to use PathMapper**

Replace the beginning of `_execute_file_read`:

```python
    def _execute_file_read(self, params: Dict) -> Observation:
        """Read file content."""
        import os
        path = params.get('path', '')
        encoding = params.get('encoding', 'utf-8')

        try:
            resolved_path = self.path_mapper.resolve(path)
            safe_path = self.validator.sanitize_path(resolved_path)

            if not os.path.exists(safe_path):
                return Observation(
                    status='error',
                    result=f'File not found: {path}',
                    execution_time=0.0,
                    metadata={}
                )
            # ... rest of the method unchanged ...
```

- [ ] **Step 4: Modify _execute_file_write to use PathMapper**

Replace the beginning of `_execute_file_write`:

```python
    def _execute_file_write(self, params: Dict) -> Observation:
        """Write content to file."""
        import os
        path = params.get('path', '')
        content = params.get('content', '')
        encoding = params.get('encoding', 'utf-8')

        try:
            resolved_path = self.path_mapper.resolve(path)
            safe_path = self.validator.sanitize_path(resolved_path)

            dir_path = os.path.dirname(safe_path)
            if dir_path and not os.path.exists(dir_path):
                os.makedirs(dir_path)
            # ... rest of the method unchanged ...
```

- [ ] **Step 5: Modify _execute_file_delete to use PathMapper**

In `_execute_file_delete`, after the path validation block, add resolution before the existence check:

```python
        try:
            resolved_path = self.path_mapper.resolve(path)
            full_path = self.validator.sanitize_path(resolved_path)
        except Exception as e:
            return Observation(
                status='error',
                result=str(e),
                execution_time=0.0,
                metadata={'path': path}
            )

        if not os.path.exists(full_path):
            # ... existing code ...
```

Remove or update the old `validate_sandbox_path` check if it blocks real paths — actually keep it as a fallback, but let `path_mapper.resolve` handle the translation first. Simpler: replace the old validation with:

```python
        try:
            resolved_path = self.path_mapper.resolve(path)
            full_path = self.validator.sanitize_path(resolved_path)
        except Exception as e:
            return Observation(
                status='error',
                result=str(e),
                execution_time=0.0,
                metadata={'path': path}
            )

        if not os.path.exists(full_path):
            return Observation(
                status='error',
                result=f'文件或目录不存在: {path}',
                execution_time=0.0,
                metadata={'path': path}
            )
        # ... continue with confirmed check and deletion ...
```

- [ ] **Step 6: Update terminal execution working_dir mapping**

Find where `terminal` tool handles `working_dir` (around line 811 in current `l5_tools.py`):

```python
        working_dir = params.get('working_dir', '.')
        try:
            if working_dir != '.':
                resolved_dir = self.path_mapper.resolve(working_dir)
                safe_dir = self.validator.sanitize_path(resolved_dir)
            else:
                safe_dir = '.'
        except Exception as e:
            return Observation(
                status='error',
                result=str(e),
                execution_time=0.0,
                metadata={}
            )
```

- [ ] **Step 7: Update permission checks to use resolved paths**

Find `_check_permission` (or inline permission checks) in `ToolsCapabilities.execute` for `file_reader`, `file_writer`, `file_delete`, `terminal`. Before `self.permission_manager.check_permission(tool_name, path)`, resolve the path:

```python
            # Resolve path for permission check
            resolved = self.path_mapper.resolve(path)
            permission = self.permission_manager.check_permission(tool_name, resolved)
```

Do this for all tools that accept a `path` or `working_dir`.

- [ ] **Step 8: Write integration test**

Add to `src/l5/tests/test_l5.py`:

```python
import tempfile
import os

def test_file_write_resolves_desktop_alias():
    from src.l5.l5_tools import ToolsCapabilities
    tools = ToolsCapabilities()

    # Use a mock home via environment if needed, or just verify the path ends with Desktop
    result = tools.execute(
        "file_writer",
        {"path": "桌面/test_vclaw_path.txt", "content": "hello from desktop"},
        user_permissions=[],
        timeout=30
    )
    assert result.status == "success"
    assert "Desktop" in result.metadata.get("path", "")
```

If this test is too intrusive for the real Desktop, instead unit-test `path_mapper.resolve` directly in `test_path_mapper.py` (already done in Task 1).

- [ ] **Step 9: Run L5 tests**

```bash
pytest src/l5/tests/ -v
```

Expected: all pass

- [ ] **Step 10: Commit**

```bash
git add src/l5/l5_tools.py src/l5/tests/test_l5.py
git commit -m "feat(l5): integrate PathMapper into file and terminal tools"
```

---

### Task 4: 更新 L3 系统提示词

**Files:**
- Modify: `src/l3/l3_orchestration.py`
- Test: `src/l3/tests/test_l3.py`

- [ ] **Step 1: Update `_build_messages` system prompt**

In `src/l3/l3_orchestration.py`, find the `FILE PATH HANDLING` block inside `_build_messages` and replace it with:

```python
FILE PATH HANDLING:
When the user mentions a file path in natural language (e.g., "桌面", "下载", "文档"),
simply pass the path as-is in the tool parameters. The system will automatically resolve it.
Examples:
- "桌面/文件.txt" -> the user's real Desktop
- "下载/报告.pdf" -> the user's real Downloads folder
- "文档/笔记.md" -> the user's real Documents folder
- Single filename like "test.txt" -> defaults to Documents folder
- "documents/..." -> project sandbox directory (backward compatible)
```

- [ ] **Step 2: Update ReActEngine prompt as well**

In the same file, find `ReActEngine.generate_thought` and its `react_prompt`. Replace Rule 5:

```
5. For file operations, use natural language paths (e.g., "桌面/文件.txt", "文档/报告.md")
```

- [ ] **Step 3: Check and fix any failing L3 tests**

Run:

```bash
pytest src/l3/tests/test_l3.py -v
```

If any test asserts that LLM output contains `documents/desktop`, update those assertions to expect natural language paths like `桌面/` or `Desktop/`.

Specifically check `src/l3/tests/test_file_path_handling.py` if it exists.

- [ ] **Step 4: Commit**

```bash
git add src/l3/l3_orchestration.py src/l3/tests/test_l3.py
git commit -m "feat(l3): update prompts to use natural language paths instead of hardcoded documents/ mapping"
```

---

### Task 5: 文档同步

**Files:**
- Modify: `src/l5/tests/README.md`
- Modify: `docs/L3_Orchestration.xml`
- Modify: `CLAUDE.md`

- [ ] **Step 1: Update `src/l5/tests/README.md`**

Add a row for the new test file:

```markdown
| `test_path_mapper.py` | `pytest` | `pytest src/l5/tests/test_path_mapper.py -v` |
```

Add dependency row if needed:

```markdown
| `test_path_mapper.py` | 无额外依赖 | 内置 `pathlib`, `os` |
```

- [ ] **Step 2: Update `docs/L3_Orchestration.xml`**

Find the section describing L3 system prompt / file path handling and update to reflect the new natural language path approach.

If the XML contains:
```xml
"桌面" or "desktop" -> documents/desktop
```
Replace with:
```xml
"桌面/文件.txt" -> resolved to real Desktop by L5 PathMapper
"documents/..." -> project sandbox (backward compatible)
```

- [ ] **Step 3: Update `CLAUDE.md`**

Find the `L3_SYSTEM_PROMPT` block in `CLAUDE.md` and update the `FILE PATH HANDLING` section to match the new L3 prompt.

- [ ] **Step 4: Commit**

```bash
git add src/l5/tests/README.md docs/L3_Orchestration.xml CLAUDE.md
git commit -m "docs: sync path mapping design to tests README, XML arch doc, and CLAUDE.md"
```

---

### Task 6: 最终回归测试

- [ ] **Step 1: Run全部相关测试**

```bash
pytest src/l3/tests/ src/l5/tests/ -v
```

- [ ] **Step 2: 手动验证 E2E**

启动 Web Console：

```bash
python src/l1/tests/web_console/server.py
```

在 E2E 对话中测试：
1. "帮我在桌面上建个文档，写今天下午3点开周会"
2. 验证文件真实创建在 `C:\Users\<user>\Desktop\周会提醒.txt`

- [ ] **Step 3: Commit if tests pass**

If all good, optionally add a final verification note or tag.

---

## Spec Coverage Checklist

| 需求 | 对应 Task |
|------|-----------|
| 新建 PathMapper 解析服务 | Task 1 |
| 真实路径权限分级 | Task 2 |
| L5 工具集成 PathMapper | Task 3 |
| L3 提示词更新 | Task 4 |
| 文档同步 | Task 5 |
| E2E 验证 | Task 6 |

**无遗漏，无占位符。**

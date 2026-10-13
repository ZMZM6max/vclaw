# L5 工具层增强提案

基于对 Claude Code 工具层代码的深入分析，结合 VClaw 当前 L5 实现，提出以下增强建议。

---

## 一、Claude Code 工具层核心特性分析

### 1. 权限系统 (Permissions)

**核心组件：**
- `PermissionMode` - 权限模式（read-only, ask, auto-apply）
- `PermissionResult` - 权限检查结果
- `filesystem.ts` - 文件系统权限检查
- `shellRuleMatching.ts` - 通配符规则匹配

**关键功能：**
- 通配符支持（`**/*.py`, `src/**`）
- 读写执行权限分离
- 基于路径的权限规则
- 权限规则配置文件

### 2. 工具执行框架 (Tool Framework)

**核心组件：**
- `buildTool` - 统一工具构建器
- `ToolDef` - 工具定义接口
- `ToolUseContext` - 工具调用上下文
- `ToolCallProgress` - 工具调用进度

**关键功能：**
- Zod Schema 输入验证
- 统一的权限检查入口
- 工具结果格式化
- 工具执行进度跟踪
- 大结果分片存储

### 3. Bash 工具增强

**核心组件：**
- `bashPermissions.ts` - Bash 权限管理
- `commandSemantics.ts` - 命令语义分析
- `readOnlyValidation.ts` - 只读验证
- `gitOperationTracking.ts` - Git 操作跟踪

**关键功能：**
- 命令分类（搜索/读取/列表/静默）
- 复杂命令解析（sed、管道）
- 沙盒管理（SandboxManager）
- 进度显示（2秒后显示进度提示）
- 超时控制（默认/最大超时）
- Git 操作检测（commit、push、pr）

### 4. 文件操作增强

**核心功能：**
- 图像处理（缩放、压缩、格式转换）
- PDF 读取（分页、页数限制）
- Notebook 文件支持
- 文件编码检测
- 行号添加
- 大文件限制（token 数限制）
- 文件历史跟踪

### 5. 任务管理 (Task Management)

**核心组件：**
- `TaskCreateTool` - 任务创建
- `TaskListTool` - 任务列表
- `TaskUpdateTool` - 任务更新
- `TaskOutputTool` - 任务输出

**关键功能：**
- 任务生命周期管理
- 任务状态跟踪（pending/in_progress/completed）
- 任务元数据支持
- 任务钩子（hooks）

### 6. MCP 支持

**核心功能：**
- 外部工具动态注册
- MCP 工具代理
- 权限透传

---

## 二、VClaw L5 当前状态

### 已实现功能

| 功能 | 状态 | 说明 |
|------|------|------|
| 工具注册表 | ✅ | ToolRegistry 支持动态注册/注销 |
| 参数验证 | ✅ | ParameterValidator 基础验证 |
| 基础工具 | ✅ | python_repl, calculator, search_web, file_reader, file_writer, file_delete, terminal |
| 沙盒路径验证 | ✅ | 强制 `documents/` 前缀 |
| 二次确认机制 | ✅ | file_delete 高危操作确认 |
| 结果格式化 | ✅ | Observation 统一输出 |

### 待增强功能

| 功能 | 优先级 | 说明 |
|------|--------|------|
| 权限系统 | 高 | 细粒度读写权限控制 |
| Bash 命令分析 | 高 | 命令语义分类、管道支持 |
| 任务管理 | 中 | 任务生命周期管理 |
| 文件类型处理 | 中 | 图像/PDF/Notebook 支持 |
| MCP 支持 | 中 | 外部工具动态注册 |
| Git 操作跟踪 | 低 | 分析 git 命令并记录 |
| 工具进度跟踪 | 低 | 长时间操作进度显示 |

---

## 三、具体增强建议

### 1. 权限系统增强（高优先级）

**建议实现：**

```python
# src/l5/permissions.py
class PermissionMode(Enum):
    READ_ONLY = "read_only"      # 只允许读取操作
    ASK = "ask"                  # 需要用户确认
    AUTO_APPLY = "auto_apply"    # 自动执行

class PermissionRule:
    """权限规则定义"""
    def __init__(self, pattern: str, mode: PermissionMode, tools: List[str] = None):
        self.pattern = pattern          # 通配符模式，如 "documents/**"
        self.mode = mode
        self.tools = tools or []        # 适用的工具列表

class PermissionManager:
    """权限管理器"""
    def __init__(self):
        self.rules: List[PermissionRule] = []
    
    def add_rule(self, rule: PermissionRule):
        """添加权限规则"""
        self.rules.append(rule)
    
    def check_permission(self, tool_name: str, path: str) -> PermissionResult:
        """检查权限"""
        # 1. 匹配通配符规则
        # 2. 返回权限结果（允许/拒绝/需要确认）
        pass
    
    def match_wildcard(self, pattern: str, path: str) -> bool:
        """通配符匹配（支持 ** 和 *）"""
        # 实现类似 fnmatch 的功能
        pass
```

**使用示例：**

```python
# 配置权限规则
perm_manager = PermissionManager()
perm_manager.add_rule(PermissionRule("documents/**", PermissionMode.AUTO_APPLY))
perm_manager.add_rule(PermissionRule("config/**", PermissionMode.READ_ONLY))
perm_manager.add_rule(PermissionRule("**/*.key", PermissionMode.ASK, tools=["file_delete"]))
```

### 2. Bash 命令分析增强（高优先级）

**建议实现：**

```python
# src/l5/bash_analyzer.py
class BashCommandType(Enum):
    SEARCH = "search"           # 搜索类（grep, find）
    READ = "read"              # 读取类（cat, head, tail）
    LIST = "list"              # 列表类（ls, tree）
    WRITE = "write"            # 写入类（cp, mv, rm）
    SILENT = "silent"          # 静默类（cd, export）
    UNKNOWN = "unknown"

class BashAnalyzer:
    """Bash 命令分析器"""
    
    SEARCH_COMMANDS = {'grep', 'find', 'rg', 'ag', 'ack'}
    READ_COMMANDS = {'cat', 'head', 'tail', 'less', 'more', 'wc', 'stat', 'file'}
    LIST_COMMANDS = {'ls', 'tree', 'du'}
    WRITE_COMMANDS = {'cp', 'mv', 'rm', 'mkdir', 'touch', 'chmod'}
    SILENT_COMMANDS = {'cd', 'export', 'unset', 'echo', 'printf'}
    
    @staticmethod
    def analyze_command(command: str) -> BashCommandType:
        """分析命令类型"""
        # 1. 解析命令（处理管道和逻辑运算符）
        # 2. 识别主命令类型
        # 3. 返回命令分类
        pass
    
    @staticmethod
    def is_git_operation(command: str) -> Optional[GitOperation]:
        """检测是否为 Git 操作"""
        # 检测 git commit, git push, gh pr create 等
        pass
    
    @staticmethod
    def is_destructive(command: str) -> bool:
        """检查是否为破坏性操作"""
        # rm, mv, git reset --hard 等
        pass
    
    @staticmethod
    def parse_pipeline(command: str) -> List[str]:
        """解析管道命令"""
        # 处理 `cat file | grep pattern | wc -l`
        pass
```

### 3. 任务管理工具（中优先级）

**建议实现：**

```python
# src/l5/task_manager.py
from enum import Enum
from typing import Optional, List
from datetime import datetime

class TaskStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class Task:
    """任务定义"""
    def __init__(self, subject: str, description: str, **kwargs):
        self.id = str(uuid.uuid4())
        self.subject = subject
        self.description = description
        self.status = TaskStatus.PENDING
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
        self.metadata = kwargs.get('metadata', {})
        self.active_form = kwargs.get('active_form')  # 进行中的描述
        self.owner = kwargs.get('owner')  # 代理ID
        self.blocks: List[str] = []  # 阻塞的任务ID
        self.blocked_by: List[str] = []  # 被哪些任务阻塞

class TaskManager:
    """任务管理器"""
    def __init__(self):
        self._tasks: Dict[str, Task] = {}
    
    def create(self, subject: str, description: str, **kwargs) -> Task:
        """创建任务"""
        task = Task(subject, description, **kwargs)
        self._tasks[task.id] = task
        return task
    
    def update(self, task_id: str, status: TaskStatus = None, **kwargs) -> Task:
        """更新任务"""
        task = self._tasks.get(task_id)
        if not task:
            raise TaskNotFoundError(f"Task {task_id} not found")
        if status:
            task.status = status
        task.metadata.update(kwargs.get('metadata', {}))
        task.updated_at = datetime.now()
        return task
    
    def list_tasks(self, status: TaskStatus = None, owner: str = None) -> List[Task]:
        """列出任务"""
        tasks = list(self._tasks.values())
        if status:
            tasks = [t for t in tasks if t.status == status]
        if owner:
            tasks = [t for t in tasks if t.owner == owner]
        return tasks
    
    def get(self, task_id: str) -> Optional[Task]:
        """获取任务"""
        return self._tasks.get(task_id)
    
    def delete(self, task_id: str):
        """删除任务"""
        if task_id in self._tasks:
            del self._tasks[task_id]
    
    def set_dependency(self, task_id: str, blocked_by: str):
        """设置任务依赖"""
        task = self._tasks.get(task_id)
        blocker = self._tasks.get(blocked_by)
        if task and blocker:
            task.blocked_by.append(blocked_by)
            blocker.blocks.append(task_id)
```

**工具集成：**

```python
# 在 ToolsCapabilities 中添加任务管理工具
def _execute_task_create(self, params: Dict) -> Observation:
    """创建任务"""
    task = self.task_manager.create(
        subject=params.get("subject"),
        description=params.get("description"),
        metadata=params.get("metadata", {})
    )
    return Observation(
        status="success",
        result=f"Created task: {task.subject} (ID: {task.id})",
        metadata={"task_id": task.id}
    )

def _execute_task_list(self, params: Dict) -> Observation:
    """列出任务"""
    status = params.get("status")
    tasks = self.task_manager.list_tasks(
        status=TaskStatus(status) if status else None
    )
    task_list = "\n".join([f"- [{t.status.value}] {t.subject}" for t in tasks])
    return Observation(
        status="success",
        result=f"Tasks:\n{task_list}",
        metadata={"count": len(tasks)}
    )

def _execute_task_update(self, params: Dict) -> Observation:
    """更新任务状态"""
    task = self.task_manager.update(
        task_id=params.get("task_id"),
        status=TaskStatus(params.get("status"))
    )
    return Observation(
        status="success",
        result=f"Updated task: {task.subject} -> {task.status.value}"
    )
```

### 4. 文件类型处理增强（中优先级）

**建议实现：**

```python
# src/l5/file_handlers.py
from abc import ABC, abstractmethod
from typing import BinaryIO

class FileHandler(ABC):
    """文件处理器基类"""
    
    @abstractmethod
    def can_handle(self, path: str) -> bool:
        """是否能处理此文件"""
        pass
    
    @abstractmethod
    def read(self, path: str, **options) -> str:
        """读取文件内容"""
        pass

class ImageFileHandler(FileHandler):
    """图像文件处理器"""
    
    SUPPORTED_FORMATS = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp'}
    
    def can_handle(self, path: str) -> bool:
        ext = Path(path).suffix.lower()
        return ext in self.SUPPORTED_FORMATS
    
    def read(self, path: str, max_width: int = 1024, max_height: int = 1024, **options) -> str:
        """读取图像，支持缩放"""
        from PIL import Image
        
        with Image.open(path) as img:
            # 缩放图像
            img.thumbnail((max_width, max_height))
            # 返回图像信息（或转换为 base64）
            return f"[Image: {img.size[0]}x{img.size[1]}, {img.format}]"

class PDFFileHandler(FileHandler):
    """PDF 文件处理器"""
    
    def can_handle(self, path: str) -> bool:
        return path.lower().endswith('.pdf')
    
    def read(self, path: str, pages: str = None, **options) -> str:
        """读取 PDF，支持分页"""
        import PyPDF2
        
        text_parts = []
        with open(path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            total_pages = len(reader.pages)
            
            # 解析页码范围
            page_range = self._parse_page_range(pages, total_pages)
            
            for page_num in page_range:
                page = reader.pages[page_num]
                text_parts.append(f"--- Page {page_num + 1} ---\n")
                text_parts.append(page.extract_text())
        
        return "\n".join(text_parts)
    
    def _parse_page_range(self, pages: str, total: int) -> List[int]:
        """解析页码范围（如 "1-5" 或 "1,3,5"）"""
        if not pages:
            return list(range(min(10, total)))  # 默认前10页
        # 实现页码解析逻辑
        pass

class NotebookFileHandler(FileHandler):
    """Jupyter Notebook 处理器"""
    
    def can_handle(self, path: str) -> bool:
        return path.lower().endswith('.ipynb')
    
    def read(self, path: str, **options) -> str:
        """读取 Notebook，提取代码和输出"""
        import json
        
        with open(path, 'r', encoding='utf-8') as f:
            notebook = json.load(f)
        
        cells = []
        for i, cell in enumerate(notebook.get('cells', [])):
            cell_type = cell.get('cell_type', 'code')
            source = ''.join(cell.get('source', []))
            cells.append(f"## Cell {i+1} ({cell_type})\n{source}\n")
        
        return "\n".join(cells)

class FileHandlerRegistry:
    """文件处理器注册表"""
    
    def __init__(self):
        self._handlers: List[FileHandler] = []
    
    def register(self, handler: FileHandler):
        """注册处理器"""
        self._handlers.append(handler)
    
    def get_handler(self, path: str) -> Optional[FileHandler]:
        """获取能处理此文件的处理器"""
        for handler in self._handlers:
            if handler.can_handle(path):
                return handler
        return None
```

### 5. MCP 支持（中优先级）

**建议实现：**

```python
# src/l5/mcp_support.py
class MCPToolDefinition:
    """MCP 工具定义"""
    def __init__(self, name: str, description: str, input_schema: Dict):
        self.name = name
        self.description = description
        self.input_schema = input_schema

class MCPClient:
    """MCP 客户端"""
    
    def __init__(self, server_url: str):
        self.server_url = server_url
        self._tools: List[MCPToolDefinition] = []
    
    async def connect(self):
        """连接到 MCP 服务器"""
        # 初始化连接，获取可用工具列表
        pass
    
    async def list_tools(self) -> List[MCPToolDefinition]:
        """获取 MCP 服务器提供的工具列表"""
        pass
    
    async def call_tool(self, tool_name: str, params: Dict) -> Dict:
        """调用 MCP 工具"""
        pass

class MCPToolAdapter:
    """MCP 工具适配器 - 将外部 MCP 工具包装为 L5 工具"""
    
    def __init__(self, mcp_client: MCPClient):
        self.mcp_client = mcp_client
    
    async def register_mcp_tools(self, registry: ToolRegistry):
        """将 MCP 工具注册到 L5 工具注册表"""
        tools = await self.mcp_client.list_tools()
        for tool_def in tools:
            # 创建适配器工具
            tool = self._create_tool_wrapper(tool_def)
            registry.register(tool_def.name, tool)
    
    def _create_tool_wrapper(self, tool_def: MCPToolDefinition) -> Tool:
        """为 MCP 工具创建包装器"""
        async def wrapper(params: Dict) -> Observation:
            result = await self.mcp_client.call_tool(tool_def.name, params)
            return Observation(
                status="success",
                result=result.get("output", ""),
                metadata=result.get("metadata", {})
            )
        
        return Tool(
            name=tool_def.name,
            description=tool_def.description,
            parameters=tool_def.input_schema,
            handler=wrapper
        )
```

### 6. Git 操作跟踪（低优先级）

**建议实现：**

```python
# src/l5/git_tracker.py
from dataclasses import dataclass
from typing import Optional

@dataclass
class GitOperation:
    operation: str           # commit, push, merge, etc.
    repository: Optional[str]
    branch: Optional[str]
    commit_id: Optional[str]
    pr_number: Optional[int]
    pr_url: Optional[str]

class GitOperationTracker:
    """Git 操作跟踪器"""
    
    # 正则表达式模式
    GIT_COMMIT_RE = re.compile(r'\bgit\s+(?:-[cC]\s+\S+\s+)*\s*commit\b')
    GIT_PUSH_RE = re.compile(r'\bgit\s+(?:-[cC]\s+\S+\s+)*\s*push\b')
    GH_PR_CREATE_RE = re.compile(r'\bgh\s+pr\s+create\b')
    
    def analyze_command(self, command: str) -> Optional[GitOperation]:
        """分析命令中的 Git 操作"""
        if self.GIT_COMMIT_RE.search(command):
            return GitOperation(operation="commit")
        elif self.GIT_PUSH_RE.search(command):
            return GitOperation(operation="push")
        elif self.GH_PR_CREATE_RE.search(command):
            return GitOperation(operation="pr_create")
        return None
    
    def parse_commit_output(self, stdout: str) -> Optional[str]:
        """从 git commit 输出中解析 commit ID"""
        # 解析 [branch abc1234] message
        match = re.search(r'\[\S+\s+([a-f0-9]{7,})\]', stdout)
        return match.group(1) if match else None
    
    def parse_pr_url(self, stdout: str) -> Optional[str]:
        """从输出中解析 PR URL"""
        match = re.search(r'https://github\.com/[^/\s]+/[^/\s]+/pull/\d+', stdout)
        return match.group(0) if match else None
    
    def record_operation(self, operation: GitOperation):
        """记录 Git 操作到分析系统"""
        # 可用于统计、审计等
        pass
```

---

## 四、实施建议

### 阶段一：核心增强（高优先级）

1. **权限系统**
   - 实现 `PermissionManager`
   - 添加通配符匹配
   - 集成到 `ToolsCapabilities`

2. **Bash 分析器**
   - 实现 `BashAnalyzer`
   - 命令分类
   - Git 操作检测

### 阶段二：功能扩展（中优先级）

3. **任务管理**
   - 实现 `TaskManager`
   - 添加 task_create, task_list, task_update 工具

4. **文件处理**
   - 实现 `FileHandlerRegistry`
   - 添加图像、PDF、Notebook 处理器

### 阶段三：高级特性（低优先级）

5. **MCP 支持**
   - 实现 `MCPClient`
   - 添加外部工具动态注册

6. **分析跟踪**
   - Git 操作跟踪
   - 工具使用统计

---

## 五、总结

通过借鉴 Claude Code 工具层的优秀设计，VClaw L5 层可以在以下方面获得显著提升：

1. **安全性** - 细粒度权限控制、破坏性操作检测
2. **可用性** - 任务管理、进度跟踪、丰富的文件处理
3. **扩展性** - MCP 支持、动态工具注册
4. **可观测性** - Git 操作跟踪、使用分析

建议按优先级分阶段实施，优先完成权限系统和 Bash 分析器，这两项对安全性和用户体验提升最大。

# VClaw Tools 文档

基于 Claude Code 工具架构实现的一套完整工具集。

## 工具列表

| 工具名 | 功能 | 分类 |
|--------|------|------|
| `file_read` | 读取文件（支持文本、图片、PDF） | 文件操作 |
| `file_write` | 写入/创建文件 | 文件操作 |
| `file_edit` | 编辑文件（字符串替换） | 文件操作 |
| `glob` | 文件搜索（glob 模式） | 文件搜索 |
| `grep` | 内容搜索（正则表达式） | 文件搜索 |
| `bash` | 执行命令行命令 | 系统 |
| `web_search` | 网络搜索 | 网络 |
| `web_fetch` | 获取网页内容 | 网络 |
| `todo_write` | 任务列表管理 | 项目管理 |

## 快速开始

```python
import asyncio
from src.tools import tool_manager

async def main():
    # 列出所有工具
    print(tool_manager.list_tools())
    
    # 调用工具
    result = await tool_manager.call("bash", command="ls -la")
    print(result.content)

asyncio.run(main())
```

## 工具详情

### 1. file_read - 文件读取

读取文件内容，支持文本、图片、PDF。

**参数：**
- `file_path` (string, required): 文件绝对路径
- `offset` (integer, optional): 起始行号（从1开始）
- `limit` (integer, optional): 最大读取行数

**示例：**
```python
from src.tools import FileReadTool

tool = FileReadTool()
result = await tool.call(
    file_path="/path/to/file.py",
    offset=1,
    limit=50
)
print(result.content)  # 带行号的文本内容
```

### 2. file_write - 文件写入

创建或覆盖文件，自动创建父目录。

**参数：**
- `file_path` (string, required): 文件绝对路径
- `content` (string, required): 文件内容

**示例：**
```python
from src.tools import FileWriteTool

tool = FileWriteTool()
result = await tool.call(
    file_path="/path/to/output.txt",
    content="Hello, World!"
)
```

### 3. file_edit - 文件编辑

基于字符串替换编辑文件。

**参数：**
- `file_path` (string, required): 文件绝对路径
- `old_string` (string, required): 要替换的文本
- `new_string` (string, required): 新文本
- `replace_all` (boolean, optional): 是否替换所有匹配项

**示例：**
```python
from src.tools import FileEditTool

tool = FileEditTool()
result = await tool.call(
    file_path="/path/to/file.py",
    old_string="def old_func():",
    new_string="def new_func():"
)
```

### 4. glob - 文件搜索

使用 glob 模式搜索文件。

**参数：**
- `pattern` (string, required): glob 模式，如 `"*.py"`, `"src/**/*.ts"`
- `path` (string, optional): 搜索目录，默认当前目录

**示例：**
```python
from src.tools import GlobTool

tool = GlobTool()
result = await tool.call(
    pattern="**/*.py",
    path="src"
)
print(result.data['filenames'])  # 匹配的文件列表
```

### 5. grep - 内容搜索

使用正则表达式搜索文件内容。

**参数：**
- `pattern` (string, required): 正则表达式
- `path` (string, optional): 搜索路径
- `glob` (string, optional): 文件过滤模式
- `output_mode` (string, optional): 输出模式 (`files_with_matches`, `content`, `count`)
- `head_limit` (integer, optional): 结果限制，默认250

**示例：**
```python
from src.tools import GrepTool

tool = GrepTool()

# 查找所有包含 "class" 的 Python 文件
result = await tool.call(
    pattern="class ",
    path="src",
    glob="*.py",
    output_mode="files_with_matches"
)

# 获取匹配内容
result = await tool.call(
    pattern="def ",
    path="src",
    output_mode="content",
    head_limit=20
)
```

### 6. bash - 命令执行

执行 Bash/PowerShell 命令。

**参数：**
- `command` (string, required): 要执行的命令
- `timeout` (integer, optional): 超时时间（秒），默认120
- `workdir` (string, optional): 工作目录

**示例：**
```python
from src.tools import BashTool

tool = BashTool()

# 执行命令
result = await tool.call(command="ls -la")

# 指定工作目录
result = await tool.call(
    command="git status",
    workdir="/path/to/repo"
)
```

### 7. web_search - 网络搜索

搜索网络信息。

**参数：**
- `query` (string, required): 搜索查询
- `num_results` (integer, optional): 结果数量（1-10），默认5

**配置：**
```bash
# Google 搜索（推荐）
export GOOGLE_API_KEY=your_api_key
export GOOGLE_CSE_ID=your_cse_id

# Bing 搜索
export BING_API_KEY=your_api_key
```

**示例：**
```python
from src.tools import WebSearchTool

tool = WebSearchTool()
result = await tool.call(
    query="Python async tutorial",
    num_results=5
)
print(result.content)
```

### 8. web_fetch - 网页获取

获取并提取网页内容。

**参数：**
- `url` (string, required): 网页 URL
- `max_length` (integer, optional): 最大内容长度，默认10000

**依赖：**
```bash
pip install requests beautifulsoup4
```

**示例：**
```python
from src.tools import WebFetchTool

tool = WebFetchTool()
result = await tool.call(
    url="https://docs.python.org/3/library/asyncio.html",
    max_length=5000
)
print(result.content)
```

### 9. todo_write - 任务管理

管理任务清单。

**参数：**
- `todos` (array, required): 任务列表
  - `content` (string): 任务内容
  - `status` (string): 状态 (`pending`, `in_progress`, `completed`)
  - `priority` (string): 优先级 (`high`, `medium`, `low`)

**示例：**
```python
from src.tools import TodoWriteTool

tool = TodoWriteTool()

# 创建任务列表
todos = [
    {"content": "Task 1", "status": "completed", "priority": "high"},
    {"content": "Task 2", "status": "in_progress", "priority": "medium"},
    {"content": "Task 3", "status": "pending", "priority": "low"}
]

result = await tool.call(todos=todos)
print(result.content)
```

## 在 L5 层使用

新工具已集成到 `ToolsCapabilities`：

```python
from src.l5_tools import ToolsCapabilities

tools = ToolsCapabilities()

# 获取所有可用工具（包括原有的和新工具）
available = tools.get_available_tools()

# 执行工具
observation = tools.execute("file_read", {
    "file_path": "src/main.py"
})
```

## 工具架构

```
src/tools/
├── __init__.py          # 导出所有工具
├── base.py              # Tool 基类和 ToolResult
├── manager.py           # ToolManager 统一管理
├── file_read.py         # FileReadTool
├── file_write.py        # FileWriteTool
├── file_edit.py         # FileEditTool
├── glob.py              # GlobTool
├── grep.py              # GrepTool
├── bash.py              # BashTool
├── web_search.py        # WebSearchTool
├── web_fetch.py         # WebFetchTool
└── todo_write.py        # TodoWriteTool
```

## 添加新工具

1. 创建工具类继承 `Tool`：

```python
from src.tools.base import Tool, ToolResult
from pydantic import BaseModel, Field

class MyToolInput(BaseModel):
    param: str = Field(..., description="参数描述")

class MyTool(Tool):
    name = "my_tool"
    description = "工具描述"
    input_schema = MyToolInput
    
    async def call(self, param: str) -> ToolResult:
        # 实现工具逻辑
        return ToolResult(success=True, content="结果")
```

2. 在 `manager.py` 中注册：

```python
from . import MyTool

# 添加到 _register_default_tools
self.register(MyTool())
```

## 测试

运行工具演示：

```bash
python examples/tools_demo.py
```

运行单元测试：

```bash
pytest tests/test_tools.py -v
```

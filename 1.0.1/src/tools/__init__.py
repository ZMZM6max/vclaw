"""VClaw Tools - Claude Code 风格的工具实现

基于 Claude Code 的工具架构，为 VClaw 项目实现了一套完整的工具集。

工具列表:
1. FileReadTool - 文件读取（支持文本、图片、PDF）
2. FileWriteTool - 文件写入/创建
3. FileEditTool - 文件编辑（基于字符串替换）
4. GlobTool - 文件搜索（glob 模式）
5. GrepTool - 内容搜索（正则表达式）
6. BashTool - 命令执行
7. WebSearchTool - 网络搜索
8. WebFetchTool - 网页获取
9. TodoWriteTool - 任务管理

设计理念:
- 每个工具都是独立的、可测试的组件
- 使用 Pydantic 进行参数验证
- 统一的 ToolResult 返回格式
- 完善的错误处理和权限检查
- 支持流式输出和进度报告
"""

from .base import Tool, ToolResult, ToolError
from .file_read import FileReadTool
from .file_write import FileWriteTool
from .file_edit import FileEditTool
from .glob import GlobTool
from .grep import GrepTool
from .bash import BashTool
from .web_search import WebSearchTool
from .web_fetch import WebFetchTool
from .todo_write import TodoWriteTool
from .manager import ToolManager, tool_manager

__all__ = [
    # 基础类
    "Tool",
    "ToolResult", 
    "ToolError",
    # 工具实现
    "FileReadTool",
    "FileWriteTool",
    "FileEditTool",
    "GlobTool",
    "GrepTool",
    "BashTool",
    "WebSearchTool",
    "WebFetchTool",
    "TodoWriteTool",
    # 管理器
    "ToolManager",
    "tool_manager",
]

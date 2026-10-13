"""L5: Tools & Capabilities Layer - Tool Registry and execution stubs."""

import re
import threading
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Union

from src.core.exceptions import ExecutionTimeoutError, ToolNotFoundError, ValidationError
from src.core.models import Observation


# ========== ToolRegistry 专用异常 ==========
class ToolAlreadyRegisteredError(Exception):
    """尝试注册已存在的工具名称."""
    pass


class InvalidToolDefinitionError(Exception):
    """工具定义不符合规范."""
    pass


class RegistryFullError(Exception):
    """注册表已满，达到 MAX_TOOLS_PER_REGISTRY 限制."""
    pass


# ========== Tool 数据类 ==========
@dataclass
class Tool:
    """工具定义对象，包含工具的所有元数据和执行引用."""
    name: str
    description: str
    parameters: Dict[str, Any]
    handler: Union[Callable, str, None] = None
    category: str = "general"
    requires_confirmation: bool = False
    timeout_default: int = 30
    returns: Optional[Dict[str, Any]] = None


# ========== ToolRegistry ==========
class ToolRegistry:
    """工具注册表，管理所有可用工具的注册、发现与生命周期.

    作为L5层的核心枢纽，维护工具名称到工具实现的映射，
    支持动态加载、热插拔和元数据查询。
    """

    TOOL_NAME_PATTERN = re.compile(r'^[a-z][a-z0-9_]*$')
    MAX_TOOLS_PER_REGISTRY = 100

    def __init__(self, auto_register: bool = True):
        self._tools: Dict[str, Tool] = {}
        self._categories: Dict[str, List[str]] = {}
        self._lock = threading.RLock()
        if auto_register:
            self._register_builtin_tools()

    def _register_builtin_tools(self):
        """系统启动时自动注册默认工具集."""
        builtins = [
            Tool(
                name="python_repl",
                description="执行Python代码片段，支持数学计算、数据处理、文本操作等",
                parameters={
                    "type": "object",
                    "properties": {
                        "code": {"type": "string", "description": "要执行的Python代码"}
                    },
                    "required": ["code"]
                },
                handler="L6_DELEGATE",
                category="code",
                timeout_default=30,
                requires_confirmation=False
            ),
            Tool(
                name="search_web",
                description="使用DuckDuckGo搜索网络信息，获取实时网页内容",
                parameters={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "搜索关键词"}
                    },
                    "required": ["query"]
                },
                handler=None,
                category="network",
                timeout_default=30,
                requires_confirmation=False
            ),
            Tool(
                name="file_read",
                description="读取指定路径的文件内容，支持文本文件",
                parameters={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "文件路径（相对或绝对路径）"}
                    },
                    "required": ["path"]
                },
                handler=None,
                category="file",
                timeout_default=10,
                requires_confirmation=False
            ),
            Tool(
                name="file_write",
                description="将内容写入指定路径的文件，支持新建和覆盖",
                parameters={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "文件路径"},
                        "content": {"type": "string", "description": "要写入的文件内容"}
                    },
                    "required": ["path", "content"]
                },
                handler=None,
                category="file",
                timeout_default=10,
                requires_confirmation=True
            ),
            Tool(
                name="file_delete",
                description="删除指定路径的文件或清空目录",
                parameters={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "要删除的文件或目录路径"}
                    },
                    "required": ["path"]
                },
                handler=None,
                category="file",
                timeout_default=10,
                requires_confirmation=True
            ),
            Tool(
                name="terminal",
                description="执行终端命令（bash/shell），支持文件操作、系统命令等",
                parameters={
                    "type": "object",
                    "properties": {
                        "command": {"type": "string", "description": "要执行的终端命令"}
                    },
                    "required": ["command"]
                },
                handler="L6_DELEGATE",
                category="system",
                timeout_default=30,
                requires_confirmation=True
            ),
            Tool(
                name="calculator",
                description="执行数学计算表达式，支持基本运算、函数、变量",
                parameters={
                    "type": "object",
                    "properties": {
                        "expression": {"type": "string", "description": "数学表达式，如 \"1 + 2 * 3\" 或 \"sin(pi/2)\""}
                    },
                    "required": ["expression"]
                },
                handler=None,
                category="math",
                timeout_default=5,
                requires_confirmation=False
            ),
            Tool(
                name="file_search",
                description="模糊文件搜索，根据关键词或部分文件名查找文件位置",
                parameters={
                    "type": "object",
                    "properties": {
                        "keyword": {"type": "string", "description": "搜索关键词或部分文件名"},
                        "directory": {"type": "string", "description": "可选：搜索目录（默认documents/）", "default": "documents/"}
                    },
                    "required": ["keyword"]
                },
                handler=None,
                category="search",
                timeout_default=15,
                requires_confirmation=False
            ),
        ]
        for tool in builtins:
            self._tools[tool.name] = tool
            self._categories.setdefault(tool.category, []).append(tool.name)

    def register(self, name: str, tool: Tool) -> None:
        """注册一个新工具.

        Args:
            name: 工具名称（唯一标识）
            tool: 工具定义对象

        Raises:
            InvalidToolDefinitionError: 名称格式非法或参数Schema非法
            ToolAlreadyRegisteredError: 工具已存在
            RegistryFullError: 注册表已满
        """
        if not self.TOOL_NAME_PATTERN.match(name):
            raise InvalidToolDefinitionError(
                f"Tool name '{name}' must match pattern ^[a-z][a-z0-9_]*$"
            )
        if not isinstance(tool.parameters, dict):
            raise InvalidToolDefinitionError("tool.parameters must be a dict")

        with self._lock:
            if name in self._tools:
                raise ToolAlreadyRegisteredError(f"Tool '{name}' is already registered")
            if len(self._tools) >= self.MAX_TOOLS_PER_REGISTRY:
                raise RegistryFullError(f"Registry is full (max {self.MAX_TOOLS_PER_REGISTRY})")

            self._tools[name] = tool
            self._categories.setdefault(tool.category, []).append(name)

    def unregister(self, name: str) -> bool:
        """注销一个工具.

        Args:
            name: 要注销的工具名称

        Returns:
            是否成功注销（不存在返回False）
        """
        with self._lock:
            if name not in self._tools:
                return False
            tool = self._tools.pop(name)
            if tool.category in self._categories:
                try:
                    self._categories[tool.category].remove(name)
                except ValueError:
                    pass
            return True

    def get(self, name: str) -> Optional[Tool]:
        """通过名称获取工具.

        Args:
            name: 工具名称

        Returns:
            工具定义对象，不存在返回None
        """
        return self._tools.get(name)

    def has_tool(self, name: str) -> bool:
        """检查工具是否已注册.

        Args:
            name: 工具名称

        Returns:
            是否已注册
        """
        return name in self._tools

    def list_tools(self, category: Optional[str] = None, include_internal: bool = False) -> List[Tool]:
        """列出所有已注册工具.

        Args:
            category: 按分类筛选
            include_internal: 是否包含内部工具（如L6_DELEGATE标记的工具）

        Returns:
            工具定义列表
        """
        if category:
            names = self._categories.get(category, [])
            tools = [self._tools[n] for n in names if n in self._tools]
        else:
            tools = list(self._tools.values())

        if not include_internal:
            tools = [t for t in tools if t.handler != "L6_DELEGATE"]
        return tools

    def get_available_tools_for_llm(self, user_permissions: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """获取 OpenAI Function Calling 格式的工具列表.

        Args:
            user_permissions: 用户权限列表（当前预留，后续对接PermissionManager）

        Returns:
            符合OpenAI Function Calling格式的工具定义列表
        """
        # 包含所有工具（包括L6_DELEGATE），因为LLM需要知道这些工具的存在
        tools = self.list_tools(include_internal=True)
        result = []
        for tool in tools:
            result.append({
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters
                }
            })
        return result

    def clear(self) -> None:
        """清空所有注册的工具（主要用于测试）."""
        with self._lock:
            self._tools.clear()
            self._categories.clear()


# ========== 从子模块导入已实现的组件 ==========
from src.l5.parameter_validator import (
    ParameterValidator,
    ValidationResult,
    ValidationErrorDetail,
    FidelityCheckResult,
    FidelityMismatch,
    InvalidSchemaError,
    FidelityCheckError,
    PathTraversalError,
)
from src.l5.bash_analyzer import BashAnalyzer
from src.l5.l5_permission_manager import PermissionManager
from src.l5.result_formatter import ResultFormatter


class ToolContextBuilder:
    @staticmethod
    def build_tool_context(tools, include_examples: bool = True) -> str:
        parts = ["Available Tools:", "=" * 50]
        for tool in tools:
            parts.append(f"\nTool: {tool.name}")
            parts.append(f"   Description: {tool.description}")
        parts.append("\n" + "=" * 50)
        return "\n".join(parts)

    @staticmethod
    def format_tools_for_llm(tools) -> str:
        return "Tools: " + ", ".join([t.name for t in tools])


class ToolsCapabilities:
    """L5 工具能力层 - 整合 ToolRegistry、ToolExecutor 提供统一工具执行接口."""

    def __init__(self, runtime=None, enable_permissions=True, sandbox_documents_root=None):
        self.runtime = runtime
        self.registry = ToolRegistry()
        self.validator = ParameterValidator()
        self.result_formatter = ResultFormatter()
        self._enable_permissions = enable_permissions
        self._sandbox_documents_root = sandbox_documents_root

        # 局部导入避免循环依赖
        from src.l5.tool_executor import ToolExecutor, ExecutionContext
        from src.l5.confirmation_manager import ConfirmationManager

        self.permission_manager = PermissionManager() if enable_permissions else None
        self.bash_analyzer = BashAnalyzer()
        self.confirmation_manager = ConfirmationManager() if enable_permissions else None

        # 默认用户应用 standard_user 策略（允许大多数工具，危险操作需确认）
        if self.permission_manager is not None:
            self.permission_manager.apply_default_policy("default", "standard_user")

        self._executor = ToolExecutor(
            tool_registry=self.registry,
            parameter_validator=self.validator,
            permission_manager=self.permission_manager,
            confirmation_manager=self.confirmation_manager,
            bash_analyzer=self.bash_analyzer,
            result_formatter=self.result_formatter,
            runtime=self.runtime,
        )
        if sandbox_documents_root:
            self._executor.SANDBOX_ROOT = sandbox_documents_root
        self._ExecutionContext = ExecutionContext

    def execute(self, action_name: str, params, user_permissions=None, timeout=30):
        """执行工具调用.

        Args:
            action_name: 工具名称.
            params: 工具参数.
            user_permissions: 用户权限（当前预留）.
            timeout: 执行超时时间（秒）.

        Returns:
            Observation: 标准化的工具执行结果.
        """
        tool = self.registry.get(action_name)
        if tool is None:
            return self.result_formatter.format_error(
                error_message=f"工具 '{action_name}' 不存在",
                tool_name=action_name,
                execution_time=0.0,
                error_type="not_found",
            )

        context = self._ExecutionContext(
            tool=tool,
            params=params,
            user_id="default",
            session_id="default",
            timeout=timeout,
        )

        result = self._executor.execute(tool, params, context)

        if result.status == "error":
            return self.result_formatter.format_error(
                error_message=result.result,
                tool_name=action_name,
                execution_time=result.execution_time,
                error_type=result.metadata.get("error_type"),
            )

        if result.status == "pending_confirmation":
            return Observation(
                status="pending_confirmation",
                result=result.result,
                execution_time=result.execution_time,
                metadata=result.metadata,
            )

        return self.result_formatter.format(
            raw_result=result.result,
            tool_name=action_name,
            execution_time=result.execution_time,
            metadata=result.metadata,
        )

    def get_available_tools(self, user_permissions=None):
        return self.registry.get_available_tools_for_llm()

    def get_tools_with_descriptions(self):
        tools = self.registry.list_tools(include_internal=True)
        return ToolContextBuilder.build_tool_context(tools)

    def list_tools(self):
        return [
            {"name": t.name, "description": t.description, "parameters": t.parameters}
            for t in self.registry.list_tools()
        ]

    def format_tools_for_llm(self):
        tools = self.registry.list_tools()
        return ToolContextBuilder.format_tools_for_llm(tools)

    def register_tool(self, name, tool):
        self.registry.register(name, tool)

    def unregister_tool(self, name):
        self.registry.unregister(name)

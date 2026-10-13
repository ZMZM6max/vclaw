"""工具管理器 - 统一管理和调用工具"""
from typing import Dict, List, Any, Optional, Type
from .base import Tool, ToolResult


class ToolManager:
    """
    工具管理器
    
    统一管理所有工具的注册、发现和调用
    """
    
    def __init__(self):
        self._tools: Dict[str, Tool] = {}
        self._register_default_tools()
    
    def _register_default_tools(self):
        """注册默认工具"""
        from . import (
            FileReadTool, FileWriteTool, FileEditTool,
            GlobTool, GrepTool, BashTool,
            WebSearchTool, WebFetchTool, TodoWriteTool
        )
        
        tools = [
            FileReadTool(),
            FileWriteTool(),
            FileEditTool(),
            GlobTool(),
            GrepTool(),
            BashTool(),
            WebSearchTool(),
            WebFetchTool(),
            TodoWriteTool(),
        ]
        
        for tool in tools:
            self.register(tool)
    
    def register(self, tool: Tool):
        """
        注册工具
        
        Args:
            tool: 工具实例
        """
        self._tools[tool.name] = tool
    
    def get(self, name: str) -> Optional[Tool]:
        """
        获取工具
        
        Args:
            name: 工具名称
            
        Returns:
            工具实例或 None
        """
        return self._tools.get(name)
    
    def list_tools(self) -> List[str]:
        """
        列出所有可用工具
        
        Returns:
            工具名称列表
        """
        return list(self._tools.keys())
    
    def get_available_tools(self) -> List[Dict[str, Any]]:
        """
        获取工具定义列表（用于 LLM）
        
        Returns:
            OpenAI function 格式列表
        """
        return [tool.to_function_def() for tool in self._tools.values()]
    
    async def call(self, tool_name: str, **kwargs) -> ToolResult:
        """
        调用工具
        
        Args:
            tool_name: 工具名称
            **kwargs: 工具参数
            
        Returns:
            工具执行结果
        """
        tool = self.get(tool_name)
        if not tool:
            return ToolResult(
                success=False,
                error=f"Tool not found: {tool_name}"
            )
        
        try:
            return await tool.call(**kwargs)
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Tool execution failed: {str(e)}"
            )
    
    def get_tool_descriptions(self) -> str:
        """
        获取所有工具的文本描述
        
        Returns:
            格式化的工具描述文本
        """
        lines = ["# Available Tools\n"]
        
        for name, tool in sorted(self._tools.items()):
            lines.append(f"## {name}")
            lines.append(f"{tool.description}")
            if tool.search_hint:
                lines.append(f"*Hint: {tool.search_hint}*")
            lines.append("")
        
        return '\n'.join(lines)


# 全局工具管理器实例
tool_manager = ToolManager()

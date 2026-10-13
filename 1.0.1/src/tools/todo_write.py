"""Todo 写入工具 - 任务列表管理"""
from typing import List, Optional, Literal
from pydantic import BaseModel, Field
from .base import Tool, ToolResult


class TodoItem(BaseModel):
    """单个待办事项"""
    content: str = Field(..., description="任务内容")
    status: Literal["pending", "in_progress", "completed"] = Field("pending", description="任务状态")
    priority: Literal["high", "medium", "low"] = Field("medium", description="优先级")


class TodoWriteInput(BaseModel):
    """TodoWrite 输入参数"""
    todos: List[TodoItem] = Field(..., description="待办事项列表")


class TodoWriteTool(Tool):
    """
    管理任务清单（Todo List）
    
    功能：
    - 创建/更新任务列表
    - 标记任务状态
    - 设置优先级
    
    使用场景：
    - 多步骤任务跟踪
    - 项目进度管理
    - 复杂工作分解
    
    状态说明：
    - pending: 待处理
    - in_progress: 进行中
    - completed: 已完成
    
    优先级说明：
    - high: 高优先级（必须完成）
    - medium: 中优先级（应该完成）
    - low: 低优先级（可以完成）
    
    使用提示：
    - 任务开始前创建列表
    - 完成一项更新一项
    - 所有任务完成时清空列表
    """
    
    name = "todo_write"
    description = """管理当前会话的任务清单。用于跟踪多步骤任务的进度。

状态：
- pending: 待处理
- in_progress: 进行中  
- completed: 已完成

优先级：
- high/medium/low

使用提示：
- 复杂任务开始前创建清单
- 完成一项更新一项
- 全部完成后清空列表"""
    search_hint = "manage the session task checklist"
    read_only = False
    
    input_schema = TodoWriteInput
    max_result_size = 50_000
    
    # 类级别的任务存储（替代全局状态）
    _todos: List[dict] = []
    
    async def call(self, todos: List[dict]) -> ToolResult:
        """
        更新任务列表
        
        Args:
            todos: 任务列表，每项包含 content, status, priority
        """
        # 转换输入为内部格式
        new_todos = []
        for todo in todos:
            new_todos.append({
                "content": todo.get("content", ""),
                "status": todo.get("status", "pending"),
                "priority": todo.get("priority", "medium")
            })
        
        # 保存旧列表用于对比
        old_todos = self._todos.copy()
        self._todos = new_todos
        
        # 统计信息
        total = len(new_todos)
        completed = sum(1 for t in new_todos if t["status"] == "completed")
        in_progress = sum(1 for t in new_todos if t["status"] == "in_progress")
        pending = sum(1 for t in new_todos if t["status"] == "pending")
        
        # 格式化输出
        lines = [f"Tasks: {completed}/{total} completed\n"]
        
        for i, todo in enumerate(new_todos, 1):
            status_icon = {
                "completed": "✓",
                "in_progress": "►",
                "pending": "○"
            }.get(todo["status"], "○")
            
            priority_icon = {
                "high": "🔴",
                "medium": "🟡",
                "low": "🟢"
            }.get(todo["priority"], "⚪")
            
            lines.append(f"{i}. {status_icon} {priority_icon} {todo['content']}")
        
        content = '\n'.join(lines)
        
        # 如果全部完成，添加提示
        if total > 0 and completed == total:
            content += "\n\n✅ All tasks completed!"
        
        return ToolResult(
            success=True,
            content=content,
            data={
                "old_todos": old_todos,
                "new_todos": new_todos,
                "total": total,
                "completed": completed,
                "in_progress": in_progress,
                "pending": pending
            }
        )
    
    def get_todos(self) -> List[dict]:
        """获取当前任务列表"""
        return self._todos.copy()
    
    def clear(self):
        """清空任务列表"""
        self._todos = []

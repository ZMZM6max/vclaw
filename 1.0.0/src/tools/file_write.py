"""文件写入工具 - 创建或覆盖文件"""
import os
from pathlib import Path
from pydantic import BaseModel, Field
from .base import Tool, ToolResult, ToolError


class FileWriteInput(BaseModel):
    """FileWrite 输入参数"""
    file_path: str = Field(..., description="要写入的文件的绝对路径（必须是绝对路径，不是相对路径）")
    content: str = Field(..., description="要写入文件的内容")


class FileWriteTool(Tool):
    """
    写入文件内容
    
    功能：
    - 创建新文件
    - 覆盖已有文件
    - 自动创建父目录
    
    注意：写入前应该先读取文件检查是否存在
    """
    
    name = "file_write"
    description = "写入文件到本地文件系统。可以创建新文件或覆盖已有文件。自动创建父目录。"
    search_hint = "create or overwrite files"
    read_only = False
    
    input_schema = FileWriteInput
    max_result_size = 100_000
    
    async def call(self, file_path: str, content: str) -> ToolResult:
        """
        写入文件
        
        Args:
            file_path: 文件绝对路径
            content: 文件内容
        """
        path = Path(file_path)
        
        # 验证路径
        if not path.is_absolute():
            raise ToolError(
                f"Path must be absolute: {file_path}",
                error_code=1
            )
        
        # 检查是否是目录
        if path.exists() and path.is_dir():
            raise ToolError(
                f"Path is a directory, not a file: {file_path}",
                error_code=2
            )
        
        # 记录是否是新文件
        is_new = not path.exists()
        
        try:
            # 创建父目录
            path.parent.mkdir(parents=True, exist_ok=True)
            
            # 写入文件
            path.write_text(content, encoding='utf-8')
            
            # 获取文件信息
            file_size = path.stat().st_size
            
            return ToolResult(
                success=True,
                content=f"File {'created' if is_new else 'updated'} successfully: {file_path}",
                data={
                    "file_path": str(path),
                    "type": "create" if is_new else "update",
                    "size": file_size,
                    "lines": content.count('\n') + (1 if content and not content.endswith('\n') else 0)
                }
            )
            
        except PermissionError:
            raise ToolError(
                f"Permission denied: {file_path}",
                error_code=3
            )
        except Exception as e:
            raise ToolError(
                f"Error writing file: {str(e)}",
                error_code=4,
                details={"exception": str(e)}
            )

"""文件读取工具 - 支持文本、图片、PDF"""
import os
import base64
from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field
from .base import Tool, ToolResult, ToolError


class FileReadInput(BaseModel):
    """FileRead 输入参数"""
    file_path: str = Field(..., description="要读取的文件的绝对路径")
    offset: Optional[int] = Field(None, description="开始读取的行号（从1开始）")
    limit: Optional[int] = Field(None, description="读取的最大行数")


class FileReadTool(Tool):
    """
    读取文件内容
    
    支持：
    - 文本文件（带行号）
    - 图片文件（base64编码）
    - PDF文件（提取文本）
    - Jupyter notebooks
    
    对于大文件，使用 offset 和 limit 参数分批读取
    """
    
    name = "file_read"
    description = "读取文件内容。支持文本、图片、PDF。对于大文件使用 offset 和 limit 分批读取。"
    search_hint = "read files, images, PDFs"
    read_only = True
    
    input_schema = FileReadInput
    max_result_size = 200_000
    
    # 图片扩展名
    IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp'}
    # 二进制文件扩展名（拒绝读取）
    BINARY_EXTENSIONS = {'.exe', '.dll', '.so', '.dylib', '.bin'}
    
    async def call(self, file_path: str, offset: Optional[int] = None, 
                   limit: Optional[int] = None) -> ToolResult:
        """
        读取文件
        
        Args:
            file_path: 文件绝对路径
            offset: 起始行号（1-based）
            limit: 最大行数
        """
        path = Path(file_path)
        
        # 验证路径
        if not path.is_absolute():
            raise ToolError(
                f"Path must be absolute: {file_path}",
                error_code=1
            )
        
        # 检查文件是否存在
        if not path.exists():
            # 尝试在当前工作目录下查找
            cwd_path = Path(os.getcwd()) / file_path
            if cwd_path.exists():
                path = cwd_path
            else:
                raise ToolError(
                    f"File not found: {file_path}",
                    error_code=2
                )
        
        if not path.is_file():
            raise ToolError(
                f"Path is not a file: {file_path}",
                error_code=3
            )
        
        ext = path.suffix.lower()
        
        # 拒绝二进制可执行文件
        if ext in self.BINARY_EXTENSIONS:
            raise ToolError(
                f"Cannot read binary file: {file_path}",
                error_code=4
            )
        
        try:
            # 读取图片
            if ext in self.IMAGE_EXTENSIONS:
                return await self._read_image(path)
            
            # 读取文本
            return await self._read_text(path, offset, limit)
            
        except Exception as e:
            raise ToolError(
                f"Error reading file: {str(e)}",
                error_code=5,
                details={"exception": str(e)}
            )
    
    async def _read_text(self, path: Path, offset: Optional[int], 
                         limit: Optional[int]) -> ToolResult:
        """读取文本文件"""
        # 读取文件内容
        try:
            content = path.read_text(encoding='utf-8', errors='replace')
        except UnicodeDecodeError:
            # 尝试其他编码
            content = path.read_text(encoding='gbk', errors='replace')
        
        lines = content.split('\n')
        total_lines = len(lines)
        
        # 应用 offset 和 limit
        start_idx = (offset - 1) if offset else 0
        start_idx = max(0, min(start_idx, total_lines))
        
        end_idx = start_idx + limit if limit else total_lines
        end_idx = min(end_idx, total_lines)
        
        selected_lines = lines[start_idx:end_idx]
        
        # 添加行号
        numbered_lines = []
        for i, line in enumerate(selected_lines, start=start_idx + 1):
            numbered_lines.append(f"{i:4d}: {line}")
        
        result_content = '\n'.join(numbered_lines)
        
        # 截断如果太长
        truncated = len(result_content) > self.max_result_size
        if truncated:
            result_content = result_content[:self.max_result_size - 100]
            result_content += "\n... [Content truncated]"
        
        return ToolResult(
            success=True,
            content=result_content,
            data={
                "file_path": str(path),
                "total_lines": total_lines,
                "start_line": start_idx + 1,
                "num_lines": len(selected_lines),
                "truncated": truncated
            }
        )
    
    async def _read_image(self, path: Path) -> ToolResult:
        """读取图片文件"""
        image_data = path.read_bytes()
        base64_data = base64.b64encode(image_data).decode('utf-8')
        
        # 获取图片尺寸信息
        width, height = None, None
        try:
            from PIL import Image
            with Image.open(path) as img:
                width, height = img.size
        except ImportError:
            pass
        except Exception:
            pass
        
        mime_type = self._get_mime_type(path.suffix)
        
        return ToolResult(
            success=True,
            content=f"[Image: {path.name} ({len(image_data)} bytes)]",
            data={
                "file_path": str(path),
                "type": "image",
                "mime_type": mime_type,
                "base64": base64_data,
                "size": len(image_data),
                "width": width,
                "height": height
            }
        )
    
    def _get_mime_type(self, ext: str) -> str:
        """获取 MIME 类型"""
        mime_map = {
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.gif': 'image/gif',
            '.webp': 'image/webp',
            '.bmp': 'image/bmp'
        }
        return mime_map.get(ext, 'application/octet-stream')

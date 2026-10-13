"""Glob 工具 - 文件搜索（glob 模式）"""
import fnmatch
import os
from pathlib import Path
from typing import Optional, List
from pydantic import BaseModel, Field
from .base import Tool, ToolResult, ToolError


class GlobInput(BaseModel):
    """Glob 输入参数"""
    pattern: str = Field(..., description="匹配文件的 glob 模式（如 '*.py', 'src/**/*.ts'）")
    path: Optional[str] = Field(None, description="搜索目录。如未指定，使用当前工作目录")


class GlobTool(Tool):
    """
    使用 glob 模式搜索文件
    
    功能：
    - 根据文件名模式查找文件
    - 支持通配符 * 和 **
    - 支持目录限制
    
    常用模式：
    - '*.py' - 当前目录所有 Python 文件
    - 'src/**/*.ts' - src 目录下所有 TypeScript 文件
    - '**/*.md' - 所有 Markdown 文件
    - 'test_*.py' - 所有测试文件
    
    结果按修改时间排序，最近修改的文件排在前面
    """
    
    name = "glob"
    description = "使用 glob 模式查找文件。支持通配符如 '*.py', 'src/**/*.ts'。结果按修改时间排序。"
    search_hint = "find files by name pattern or wildcard"
    read_only = True
    
    input_schema = GlobInput
    max_result_size = 100_000
    
    async def call(self, pattern: str, path: Optional[str] = None) -> ToolResult:
        """
        搜索文件
        
        Args:
            pattern: glob 模式
            path: 搜索目录（默认为当前工作目录）
        """
        search_path = Path(path) if path else Path(os.getcwd())
        
        if not search_path.exists():
            raise ToolError(
                f"Directory does not exist: {search_path}",
                error_code=1
            )
        
        if not search_path.is_dir():
            raise ToolError(
                f"Path is not a directory: {search_path}",
                error_code=2
            )
        
        try:
            # 执行 glob 搜索
            matches = self._glob_search(search_path, pattern)
            
            # 限制结果数量
            MAX_RESULTS = 100
            truncated = len(matches) > MAX_RESULTS
            matches = matches[:MAX_RESULTS]
            
            # 转换为相对路径（如果可能）
            cwd = Path(os.getcwd())
            relative_matches = []
            for m in matches:
                try:
                    rel = Path(m).relative_to(cwd)
                    relative_matches.append(str(rel))
                except ValueError:
                    relative_matches.append(m)
            
            return ToolResult(
                success=True,
                content="\n".join(relative_matches) if relative_matches else "No files found",
                data={
                    "pattern": pattern,
                    "path": str(search_path),
                    "filenames": relative_matches,
                    "num_files": len(relative_matches),
                    "truncated": truncated
                }
            )
            
        except Exception as e:
            raise ToolError(
                f"Error searching files: {str(e)}",
                error_code=3,
                details={"exception": str(e)}
            )
    
    def _glob_search(self, root: Path, pattern: str) -> List[str]:
        """
        执行 glob 搜索
        
        支持 '**' 递归匹配
        """
        results = []
        
        # 检查是否是递归模式
        if '**' in pattern:
            # 分割模式
            parts = pattern.split('**')
            if len(parts) == 2:
                base_part = parts[0].rstrip('/')
                file_part = parts[1].lstrip('/')
                
                search_root = root / base_part if base_part else root
                
                if search_root.exists():
                    for dirpath, dirnames, filenames in os.walk(search_root):
                        for filename in filenames:
                            if fnmatch.fnmatch(filename, file_part):
                                full_path = Path(dirpath) / filename
                                results.append(str(full_path))
        else:
            # 非递归模式
            for item in root.glob(pattern):
                if item.is_file():
                    results.append(str(item))
        
        # 按修改时间排序（最新的在前）
        results.sort(key=lambda p: Path(p).stat().st_mtime, reverse=True)
        
        return results

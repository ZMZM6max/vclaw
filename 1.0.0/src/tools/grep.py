"""Grep 工具 - 文件内容搜索（正则表达式）"""
import os
import re
from pathlib import Path
from typing import Optional, List
from pydantic import BaseModel, Field
from .base import Tool, ToolResult, ToolError


class GrepInput(BaseModel):
    """Grep 输入参数"""
    pattern: str = Field(..., description="正则表达式模式，用于搜索文件内容")
    path: Optional[str] = Field(None, description="要搜索的文件或目录。默认为当前工作目录")
    glob: Optional[str] = Field(None, description="文件过滤模式（如 '*.py', '*.{ts,tsx}'）")
    output_mode: Optional[str] = Field("files_with_matches", 
                                       description='输出模式："content"显示匹配行，"files_with_matches"显示文件路径（默认），"count"显示计数')
    context: Optional[int] = Field(None, description="匹配行前后显示的行数（-C）")
    head_limit: Optional[int] = Field(250, description="限制输出前 N 行/条目，0 表示无限制")
    include: Optional[str] = Field(None, description="文件扩展名过滤（如 '.py', '.ts'）")


class GrepTool(Tool):
    """
    使用正则表达式搜索文件内容
    
    功能：
    - 在文件内容中搜索正则表达式
    - 支持多种输出模式
    - 支持上下文行显示
    - 支持文件过滤
    
    输出模式：
    - files_with_matches: 只返回匹配的文件路径列表
    - content: 返回匹配的内容行（带行号）
    - count: 返回每个文件的匹配计数
    
    性能提示：
    - 使用 head_limit 限制大结果集
    - 使用 include/glob 缩小搜索范围
    - 优先使用 files_with_matches 模式进行初步探索
    """
    
    name = "grep"
    description = """使用正则表达式搜索文件内容。

输出模式：
- files_with_matches: 返回匹配的文件路径（默认）
- content: 返回匹配的内容行（带行号）
- count: 返回每个文件的匹配计数

提示：使用 head_limit 限制大结果集，使用 include/glob 缩小搜索范围。"""
    search_hint = "search file contents with regex"
    read_only = True
    
    input_schema = GrepInput
    max_result_size = 20_000
    
    # 要排除的目录
    EXCLUDE_DIRS = {'.git', '.svn', '.hg', 'node_modules', '__pycache__', 
                    '.pytest_cache', '.venv', 'venv', 'dist', 'build'}
    
    async def call(self, pattern: str, path: Optional[str] = None,
                   glob: Optional[str] = None, output_mode: str = "files_with_matches",
                   context: Optional[int] = None, head_limit: Optional[int] = 250,
                   include: Optional[str] = None) -> ToolResult:
        """
        搜索文件内容
        
        Args:
            pattern: 正则表达式
            path: 搜索路径
            glob: 文件过滤模式
            output_mode: 输出模式
            context: 上下文行数
            head_limit: 结果限制
            include: 文件扩展名过滤
        """
        search_path = Path(path) if path else Path(os.getcwd())
        
        if not search_path.exists():
            raise ToolError(
                f"Path does not exist: {search_path}",
                error_code=1
            )
        
        try:
            # 编译正则表达式
            try:
                regex = re.compile(pattern, re.MULTILINE)
            except re.error as e:
                raise ToolError(
                    f"Invalid regex pattern: {e}",
                    error_code=2
                )
            
            # 获取要搜索的文件列表
            files_to_search = self._get_files_to_search(search_path, glob, include)
            
            # 执行搜索
            results = []
            file_matches = set()
            match_counts = {}
            
            for file_path in files_to_search:
                try:
                    file_results = self._search_file(file_path, regex, output_mode, context)
                    if file_results:
                        if output_mode == "files_with_matches":
                            file_matches.add(str(file_path))
                        elif output_mode == "count":
                            match_counts[str(file_path)] = len(file_results)
                        else:
                            results.extend(file_results)
                except Exception:
                    # 跳过无法读取的文件
                    continue
            
            # 应用 head_limit
            if head_limit and head_limit > 0:
                if output_mode == "files_with_matches":
                    file_matches = set(list(file_matches)[:head_limit])
                elif output_mode == "content":
                    results = results[:head_limit]
            
            # 生成输出
            if output_mode == "files_with_matches":
                return self._format_files_result(file_matches, pattern)
            elif output_mode == "count":
                return self._format_count_result(match_counts, pattern)
            else:  # content
                return self._format_content_result(results, pattern)
                
        except ToolError:
            raise
        except Exception as e:
            raise ToolError(
                f"Error searching: {str(e)}",
                error_code=3,
                details={"exception": str(e)}
            )
    
    def _get_files_to_search(self, path: Path, glob: Optional[str], 
                             include: Optional[str]) -> List[Path]:
        """获取要搜索的文件列表"""
        files = []
        
        if path.is_file():
            return [path]
        
        # 遍历目录
        for root, dirs, filenames in os.walk(path):
            # 过滤排除的目录
            dirs[:] = [d for d in dirs if d not in self.EXCLUDE_DIRS]
            
            for filename in filenames:
                file_path = Path(root) / filename
                
                # 应用 glob 过滤
                if glob and not self._match_glob(filename, glob):
                    continue
                
                # 应用 include 过滤
                if include and not filename.endswith(include):
                    continue
                
                # 跳过二进制文件
                if self._is_binary(file_path):
                    continue
                
                files.append(file_path)
        
        # 按修改时间排序
        files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        
        # 限制文件数量
        return files[:1000]
    
    def _match_glob(self, filename: str, glob: str) -> bool:
        """检查文件名是否匹配 glob 模式"""
        import fnmatch
        
        # 支持多个模式（逗号分隔）
        patterns = [p.strip() for p in glob.split(',')]
        return any(fnmatch.fnmatch(filename, p) for p in patterns)
    
    def _is_binary(self, file_path: Path) -> bool:
        """检查文件是否为二进制文件"""
        try:
            with open(file_path, 'rb') as f:
                chunk = f.read(1024)
                return b'\0' in chunk
        except:
            return True
    
    def _search_file(self, file_path: Path, regex: re.Pattern, 
                     output_mode: str, context: Optional[int]) -> List[dict]:
        """搜索单个文件"""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
        except:
            return []
        
        lines = content.split('\n')
        results = []
        
        if output_mode == "content":
            ctx = context or 0
            for i, line in enumerate(lines, 1):
                if regex.search(line):
                    # 添加上下文
                    start = max(0, i - 1 - ctx)
                    end = min(len(lines), i + ctx)
                    context_lines = lines[start:end]
                    
                    result_text = []
                    for j, ctx_line in enumerate(context_lines, start + 1):
                        prefix = ">>> " if j == i else "    "
                        result_text.append(f"{prefix}{j:4d}: {ctx_line}")
                    
                    results.append({
                        "file": str(file_path),
                        "line": i,
                        "text": '\n'.join(result_text)
                    })
        else:
            # files_with_matches 或 count
            matches = list(regex.finditer(content))
            if matches:
                if output_mode == "files_with_matches":
                    return [{"file": str(file_path)}]
                else:
                    return [{"file": str(file_path), "count": len(matches)}]
        
        return results
    
    def _format_files_result(self, files: set, pattern: str) -> ToolResult:
        """格式化 files_with_matches 结果"""
        cwd = Path(os.getcwd())
        relative_files = []
        for f in sorted(files):
            try:
                rel = Path(f).relative_to(cwd)
                relative_files.append(str(rel))
            except ValueError:
                relative_files.append(f)
        
        return ToolResult(
            success=True,
            content=f"Found {len(relative_files)} files matching '{pattern}':\n" + 
                    '\n'.join(relative_files) if relative_files else f"No files found matching '{pattern}'",
            data={
                "pattern": pattern,
                "num_files": len(relative_files),
                "filenames": relative_files
            }
        )
    
    def _format_count_result(self, counts: dict, pattern: str) -> ToolResult:
        """格式化 count 结果"""
        total = sum(counts.values())
        lines = [f"{count:4d}: {file}" for file, count in sorted(counts.items(), 
                                                                 key=lambda x: -x[1])]
        
        return ToolResult(
            success=True,
            content=f"Found {total} matches across {len(counts)} files:\n" + 
                    '\n'.join(lines[:50]),
            data={
                "pattern": pattern,
                "total_matches": total,
                "num_files": len(counts),
                "counts": counts
            }
        )
    
    def _format_content_result(self, results: List[dict], pattern: str) -> ToolResult:
        """格式化 content 结果"""
        if not results:
            return ToolResult(
                success=True,
                content=f"No matches found for '{pattern}'",
                data={"pattern": pattern, "matches": []}
            )
        
        output = []
        current_file = None
        for r in results:
            if r["file"] != current_file:
                current_file = r["file"]
                output.append(f"\n{current_file}")
            output.append(r["text"])
        
        return ToolResult(
            success=True,
            content=f"Found {len(results)} matches for '{pattern}':\n" + '\n'.join(output),
            data={
                "pattern": pattern,
                "num_matches": len(results),
                "matches": results
            }
        )

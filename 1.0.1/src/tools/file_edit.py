"""文件编辑工具 - 基于字符串替换编辑文件"""
from pathlib import Path
from typing import Optional, List
from pydantic import BaseModel, Field
from .base import Tool, ToolResult, ToolError


class EditOperation(BaseModel):
    """单个编辑操作"""
    old_string: str = Field(..., description="要被替换的文本")
    new_string: str = Field(..., description="用于替换的新文本")


class FileEditInput(BaseModel):
    """FileEdit 输入参数"""
    file_path: str = Field(..., description="要编辑的文件的绝对路径")
    old_string: str = Field(..., description="要被替换的文本")
    new_string: str = Field(..., description="用于替换的新文本")
    replace_all: Optional[bool] = Field(False, description="是否替换所有匹配项（默认只替换第一个）")


class FileEditTool(Tool):
    """
    编辑文件内容（基于字符串替换）
    
    功能：
    - 替换文件中的特定文本
    - 支持单次或全部替换
    - 保持文件原有格式和编码
    
    使用示例：
    - 修改函数实现
    - 更新变量名
    - 添加/删除代码行
    
    注意：编辑前应该先读取文件获取当前内容
    """
    
    name = "file_edit"
    description = """编辑已有文件。基于字符串替换进行修改。

使用规则：
1. old_string 必须完全匹配文件中的内容（包括空格和缩进）
2. new_string 将完全替换 old_string
3. 对于多行编辑，old_string 和 new_string 都应该包含完整的行
4. 如需添加内容，使用空字符串作为 old_string（不推荐）

编辑前务必先读取文件获取准确内容。"""
    search_hint = "edit existing files"
    read_only = False
    
    input_schema = FileEditInput
    max_result_size = 100_000
    
    async def call(self, file_path: str, old_string: str, new_string: str,
                   replace_all: bool = False) -> ToolResult:
        """
        编辑文件
        
        Args:
            file_path: 文件绝对路径
            old_string: 要被替换的文本
            new_string: 新文本
            replace_all: 是否替换所有匹配项
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
            raise ToolError(
                f"File not found: {file_path}",
                error_code=2
            )
        
        if not path.is_file():
            raise ToolError(
                f"Path is not a file: {file_path}",
                error_code=3
            )
        
        try:
            # 读取原始内容
            original_content = path.read_text(encoding='utf-8')
            
            # 检查 old_string 是否存在
            if old_string not in original_content:
                raise ToolError(
                    f"old_string not found in file. The text to replace must exactly match the content.",
                    error_code=4
                )
            
            # 执行替换
            if replace_all:
                new_content = original_content.replace(old_string, new_string)
                replacements = original_content.count(old_string)
            else:
                new_content = original_content.replace(old_string, new_string, 1)
                replacements = 1
            
            # 写入文件
            path.write_text(new_content, encoding='utf-8')
            
            # 计算差异
            old_lines = old_string.count('\n') + 1
            new_lines = new_string.count('\n') + 1
            
            return ToolResult(
                success=True,
                content=f"File edited successfully: {file_path}",
                data={
                    "file_path": str(path),
                    "replacements": replacements,
                    "lines_changed": abs(new_lines - old_lines),
                    "size_before": len(original_content),
                    "size_after": len(new_content)
                }
            )
            
        except ToolError:
            raise
        except Exception as e:
            raise ToolError(
                f"Error editing file: {str(e)}",
                error_code=5,
                details={"exception": str(e)}
            )
    
    async def apply_edits(self, file_path: str, 
                          edits: List[EditOperation]) -> ToolResult:
        """
        批量应用多个编辑操作
        
        Args:
            file_path: 文件路径
            edits: 编辑操作列表
        """
        path = Path(file_path)
        
        if not path.exists():
            raise ToolError(f"File not found: {file_path}", error_code=2)
        
        content = path.read_text(encoding='utf-8')
        original_content = content
        
        applied = 0
        failed = []
        
        for i, edit in enumerate(edits):
            if edit.old_string in content:
                content = content.replace(edit.old_string, edit.new_string, 1)
                applied += 1
            else:
                failed.append(i)
        
        # 写入修改后的内容
        path.write_text(content, encoding='utf-8')
        
        return ToolResult(
            success=len(failed) == 0,
            content=f"Applied {applied}/{len(edits)} edits" + 
                    (f" (failed: {failed})" if failed else ""),
            data={
                "file_path": str(path),
                "applied": applied,
                "failed": failed,
                "size_before": len(original_content),
                "size_after": len(content)
            }
        )

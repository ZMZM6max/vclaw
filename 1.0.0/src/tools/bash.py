"""Bash 工具 - 执行命令行命令"""
import os
import subprocess
from pathlib import Path
from typing import Optional, List
from pydantic import BaseModel, Field
from .base import Tool, ToolResult, ToolError


class BashInput(BaseModel):
    """Bash 输入参数"""
    command: str = Field(..., description="要执行的命令")
    timeout: Optional[int] = Field(120, description="超时时间（秒）")
    workdir: Optional[str] = Field(None, description="工作目录")


class BashTool(Tool):
    """
    执行 Bash/PowerShell 命令
    
    功能：
    - 运行任意命令行命令
    - 支持超时控制
    - 支持自定义工作目录
    - 自动检测操作系统使用正确 shell
    
    安全提示：
    - 谨慎使用可能破坏系统的命令（rm -rf, format 等）
    - 长时间运行的命令应该设置合适的 timeout
    - 命令输出超过 10000 字符会被截断
    
    常用命令示例：
    - ls -la 或 dir - 列出目录内容
    - cat file.txt 或 type file.txt - 显示文件内容
    - git status - 检查 git 状态
    - npm install - 安装依赖
    - python script.py - 运行 Python 脚本
    """
    
    name = "bash"
    description = """执行 Bash（Linux/macOS）或 PowerShell（Windows）命令。

支持：
- 文件操作（ls, cat, grep 等）
- Git 命令（git status, git log 等）
- 构建工具（npm, pip, make 等）
- 脚本执行（python, node 等）

安全提示：谨慎使用可能破坏系统的命令，设置合适的 timeout。"""
    search_hint = "execute shell commands"
    read_only = False
    
    input_schema = BashInput
    max_result_size = 100_000
    
    # 危险命令模式（仅警告，不阻止）
    DANGEROUS_PATTERNS = [
        'rm -rf /',
        'rm -rf /*',
        'format',
        'mkfs',
        'dd if=/dev/zero',
    ]
    
    async def call(self, command: str, timeout: int = 120,
                   workdir: Optional[str] = None) -> ToolResult:
        """
        执行命令
        
        Args:
            command: 要执行的命令
            timeout: 超时时间（秒）
            workdir: 工作目录
        """
        # 检查危险命令
        for pattern in self.DANGEROUS_PATTERNS:
            if pattern in command.lower():
                raise ToolError(
                    f"Dangerous command detected: '{pattern}'. This command is not allowed.",
                    error_code=1
                )
        
        # 设置工作目录
        cwd = Path(workdir) if workdir else Path(os.getcwd())
        if not cwd.exists():
            raise ToolError(
                f"Working directory does not exist: {cwd}",
                error_code=2
            )
        
        try:
            # 检测操作系统
            is_windows = os.name == 'nt'
            
            if is_windows:
                # Windows 使用 PowerShell
                shell_cmd = ['powershell', '-Command', command]
            else:
                # Linux/macOS 使用 bash
                shell_cmd = ['bash', '-c', command]
            
            # 执行命令
            result = subprocess.run(
                shell_cmd,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout,
                encoding='utf-8',
                errors='replace'
            )
            
            # 处理输出
            stdout = result.stdout
            stderr = result.stderr
            exit_code = result.returncode
            
            # 截断长输出
            max_output = 10000
            truncated = False
            if len(stdout) > max_output:
                stdout = stdout[:max_output] + "\n... [Output truncated]"
                truncated = True
            
            # 构建结果
            output_parts = []
            if stdout:
                output_parts.append(stdout)
            if stderr:
                output_parts.append(f"[stderr]\n{stderr}")
            
            content = '\n'.join(output_parts) if output_parts else "Command completed with no output"
            
            return ToolResult(
                success=exit_code == 0,
                content=content,
                data={
                    "command": command,
                    "exit_code": exit_code,
                    "stdout_length": len(result.stdout),
                    "stderr_length": len(result.stderr),
                    "truncated": truncated,
                    "workdir": str(cwd)
                }
            )
            
        except subprocess.TimeoutExpired:
            raise ToolError(
                f"Command timed out after {timeout} seconds",
                error_code=3,
                details={"timeout": timeout}
            )
        except Exception as e:
            raise ToolError(
                f"Error executing command: {str(e)}",
                error_code=4,
                details={"exception": str(e)}
            )
    
    async def call_safe(self, commands: List[str], **kwargs) -> List[ToolResult]:
        """
        批量执行命令（安全模式）
        
        每个命令失败不会中断后续命令
        """
        results = []
        for cmd in commands:
            try:
                result = await self.call(cmd, **kwargs)
                results.append(result)
            except ToolError as e:
                results.append(ToolResult(
                    success=False,
                    content=e.message,
                    error=e.message
                ))
        return results
